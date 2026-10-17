from pathlib import Path

import numpy as np

from analysis.face_detection import analyze_faces, detect_people
from analysis.pixel_stats import compute_significance, measure_pixels
from analysis.scoring import score_image
from processors.image_loader import load_image


def process_image(image_path):
    image_path = Path(image_path)

    try:
        image = load_image(image_path)
        pixels = np.asarray(image)

        stats = measure_pixels(pixels)
        hash_pixels = np.asarray(image.resize((8, 8)).convert("L"), dtype=np.float32)
        perceptual_hash = "".join(
            "1" if pixel >= hash_pixels.mean() else "0"
            for pixel in hash_pixels.flat
        )
        face_count, eyes_closed = analyze_faces(pixels) if stats.sharpness >= 40 else (0, False)
        person_count = detect_people(pixels)
        significance_score, significance_reasons = compute_significance(stats)

        return score_image(
            path=image_path,
            width=image.width,
            height=image.height,
            brightness=stats.brightness,
            contrast=stats.contrast,
            significance_score=significance_score,
            sharpness=stats.sharpness,
            underexposed_fraction=stats.underexposed_fraction,
            overexposed_fraction=stats.overexposed_fraction,
            perceptual_hash=perceptual_hash,
            face_count=face_count,
            person_count=person_count,
            eyes_closed=eyes_closed,
            extra_reasons=[reason for group in significance_reasons for reason in group],
        )
    except (OSError, ValueError, TypeError):
        return None
