from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from analysis.face_detection import detect_faces, detect_people
from analysis.scoring import score_image


def to_grayscale(rgb_pixels):
    """Luma grayscale as float32, matching the original float32 math exactly.

    Sharpness, significance and exposure stay at full resolution on purpose:
    the sharpness metric changes a lot with image size, so the blur threshold
    only holds at the original resolution.
    """
    return (
        rgb_pixels[:, :, 0].astype(np.float32) * 0.299
        + rgb_pixels[:, :, 1].astype(np.float32) * 0.587
        + rgb_pixels[:, :, 2].astype(np.float32) * 0.114
    )


def compute_significance(pixels, grayscale):
    height, width = grayscale.shape
    upper_region = grayscale[: height * 2 // 3]
    lower_region = grayscale[height * 2 // 3 :]

    upper_std = float(upper_region.std())
    lower_std = float(lower_region.std())
    global_std = float(grayscale.std())
    horizon_contrast = abs(float(upper_region.mean()) - float(lower_region.mean()))
    edge_density = float(
        np.abs(np.diff(grayscale, axis=0)).mean()
        + np.abs(np.diff(grayscale, axis=1)).mean()
    )

    score = 0.0
    if global_std > 18:
        score += 25.0
    if upper_std > 15:
        score += 20.0
    if lower_std > 10:
        score += 15.0
    if edge_density > 2.0:
        score += 20.0
    if horizon_contrast > 10:
        score += 15.0
    if upper_std > 25 and lower_std > 15:
        score += 15.0

    if upper_std < 12 and lower_std < 10 and global_std < 10:
        score -= 45.0
    if lower_region.mean() > 150 and upper_region.mean() < 170 and lower_std < 18:
        score -= 20.0

    score = max(0.0, min(100.0, score))
    return score, (
        ["scenic"] if score >= 60 else [],
        ["low_significance", "ground_only"] if score <= 35 else [],
    )


def process_image(image_path):
    image_path = Path(image_path)

    try:
        with Image.open(image_path) as source_image:
            image = ImageOps.exif_transpose(source_image).convert("RGB")
            pixels = np.asarray(image)

        grayscale = to_grayscale(pixels)
        brightness = float(grayscale.mean())
        contrast = float(grayscale.std())
        sharpness = float(
            np.var(np.diff(grayscale, axis=0))
            + np.var(np.diff(grayscale, axis=1))
        )
        underexposed_fraction = float((grayscale <= 10).mean())
        overexposed_fraction = float((grayscale >= 245).mean())
        hash_pixels = np.asarray(image.resize((8, 8)).convert("L"), dtype=np.float32)
        perceptual_hash = "".join(
            "1" if pixel >= hash_pixels.mean() else "0"
            for pixel in hash_pixels.flat
        )
        face_count = detect_faces(pixels) if sharpness >= 40 else 0
        person_count = detect_people(pixels)
        significance_score, significance_reasons = compute_significance(pixels, grayscale)

        return score_image(
            path=image_path,
            width=image.width,
            height=image.height,
            brightness=brightness,
            contrast=contrast,
            significance_score=significance_score,
            sharpness=sharpness,
            underexposed_fraction=underexposed_fraction,
            overexposed_fraction=overexposed_fraction,
            perceptual_hash=perceptual_hash,
            face_count=face_count,
            person_count=person_count,
            extra_reasons=[reason for group in significance_reasons for reason in group],
        )
    except (OSError, ValueError, TypeError):
        return None
