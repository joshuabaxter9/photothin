from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from analysis.face_detection import detect_faces, detect_people
from analysis.scoring import score_image


def process_image(image_path):
    image_path = Path(image_path)

    try:
        with Image.open(image_path) as source_image:
            image = ImageOps.exif_transpose(source_image).convert("RGB")
            pixels = np.asarray(image, dtype=np.float32)

        grayscale = (
            pixels[:, :, 0] * 0.299
            + pixels[:, :, 1] * 0.587
            + pixels[:, :, 2] * 0.114
        )
        brightness = float(grayscale.mean())
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
        face_count = (
            detect_faces(pixels.astype(np.uint8))
            if sharpness >= 40
            else 0
        )
        person_count = detect_people(pixels.astype(np.uint8))

        return score_image(
            path=image_path,
            width=image.width,
            height=image.height,
            brightness=brightness,
            sharpness=sharpness,
            underexposed_fraction=underexposed_fraction,
            overexposed_fraction=overexposed_fraction,
            perceptual_hash=perceptual_hash,
            face_count=face_count,
            person_count=person_count,
        )
    except (OSError, ValueError, TypeError):
        return None
