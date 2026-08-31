from pathlib import Path

import cv2
import numpy as np

from analysis.face_detection import detect_faces, detect_people
from analysis.scoring import score_image
from processors.image_processor import compute_significance


def _sample_interval_for_duration(duration_seconds):
    if duration_seconds <= 10:
        return 0.5
    if duration_seconds <= 60:
        return 1.5
    if duration_seconds <= 180:
        return 3.0
    return 5.0


def _analyze_frame(frame_rgb):
    pixels = np.asarray(frame_rgb, dtype=np.float32)
    grayscale = (
        pixels[:, :, 0] * 0.299
        + pixels[:, :, 1] * 0.587
        + pixels[:, :, 2] * 0.114
    )
    brightness = float(grayscale.mean())
    contrast = float(grayscale.std())
    sharpness = float(
        np.var(np.diff(grayscale, axis=0))
        + np.var(np.diff(grayscale, axis=1))
    )
    underexposed_fraction = float((grayscale <= 10).mean())
    overexposed_fraction = float((grayscale >= 245).mean())
    face_count = detect_faces(pixels.astype(np.uint8)) if sharpness >= 40 else 0
    person_count = detect_people(pixels.astype(np.uint8))
    significance_score, significance_reasons = compute_significance(pixels, grayscale)

    reasons = []
    if sharpness < 40:
        reasons.append("blurry")
    if contrast < 18:
        reasons.append("low_contrast")
    if brightness < 45 or underexposed_fraction > 0.35:
        reasons.append("too_dark")
    if brightness > 215 or overexposed_fraction > 0.35:
        reasons.append("overexposed")
    if face_count:
        reasons.append("contains_face")
    if person_count or face_count:
        reasons.append("contains_person")
    if significance_score >= 60:
        reasons.append("scenic")
    if significance_score <= 35:
        reasons.append("low_significance")
    reasons.extend(significance_reasons[0])
    reasons.extend(significance_reasons[1])

    return {
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "underexposed_fraction": underexposed_fraction,
        "overexposed_fraction": overexposed_fraction,
        "face_count": face_count,
        "person_count": person_count,
        "significance_score": significance_score,
        "reasons": list(dict.fromkeys(reasons)),
    }


def process_video(file_path):
    video_path = Path(file_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds = total_frames / fps if fps > 0 else 0.0
    sample_interval = _sample_interval_for_duration(duration_seconds)

    sampled_frames = []
    if duration_seconds <= 0:
        sample_times = [0.0]
    else:
        sample_times = []
        time_cursor = 0.0
        while time_cursor < duration_seconds - 1e-6:
            sample_times.append(time_cursor)
            time_cursor += sample_interval
        if not sample_times or sample_times[-1] != duration_seconds:
            sample_times.append(max(0.0, duration_seconds * 0.99))

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    for sample_time in sample_times:
        capture.set(cv2.CAP_PROP_POS_MSEC, sample_time * 1000.0)
        success, frame = capture.read()
        if not success or frame is None:
            continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        sampled_frames.append(_analyze_frame(frame_rgb))

    capture.release()

    if not sampled_frames:
        return None

    brightness = float(np.mean([frame["brightness"] for frame in sampled_frames]))
    contrast = float(np.mean([frame["contrast"] for frame in sampled_frames]))
    sharpness = float(np.mean([frame["sharpness"] for frame in sampled_frames]))
    underexposed_fraction = float(
        np.mean([frame["underexposed_fraction"] for frame in sampled_frames])
    )
    overexposed_fraction = float(
        np.mean([frame["overexposed_fraction"] for frame in sampled_frames])
    )
    significance_score = float(
        np.mean([frame["significance_score"] for frame in sampled_frames])
    )
    face_count = max(frame["face_count"] for frame in sampled_frames)
    person_count = max(frame["person_count"] for frame in sampled_frames)
    reasons = list(
        dict.fromkeys(
            reason
            for frame in sampled_frames
            for reason in frame["reasons"]
        )
    )

    return score_image(
        path=video_path,
        width=width or 1280,
        height=height or 720,
        brightness=brightness,
        contrast=contrast,
        significance_score=significance_score,
        sharpness=sharpness,
        underexposed_fraction=underexposed_fraction,
        overexposed_fraction=overexposed_fraction,
        face_count=face_count,
        person_count=person_count,
        extra_reasons=reasons,
    )