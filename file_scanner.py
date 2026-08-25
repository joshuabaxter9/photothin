from pathlib import Path
from processors.image_processor import process_image
from analysis.scoring import score_image

#allowed video and image extensions
SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".avif",
    ".raw",
    ".cr2", 
    ".cr3",
    ".nef",
    ".arw",
    ".dng",
    ".orf",
    ".rw2",
}
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".flv",
    ".webm",
    ".mpeg",
    ".mpg",
    ".m4v",
    ".3gp",
    ".mts",
    ".m2ts",
    ".ts",
    ".vob",
}

def scan_folder(folder_path):
    path = Path(folder_path)

    if not path.exists():
        print("Path does not exist")
        return []
    
    if not path.is_dir():
        print("Path is no a folder")
        return []
    
    results = []
    for file in path.rglob("*"):
        if not file.is_file():
            continue
        extension = file.suffix.lower()

        if extension in SUPPORTED_IMAGE_EXTENSIONS:
            result = process_image(file)
            if result is not None:
                for previous_result in results:
                    distance = sum(
                        left != right
                        for left, right in zip(
                            result.perceptual_hash, previous_result.perceptual_hash
                        )
                    )
                    if distance <= 2:
                        result = score_image(
                            path=result.path,
                            width=result.width,
                            height=result.height,
                            brightness=result.brightness,
                            sharpness=result.sharpness,
                            underexposed_fraction=result.underexposed_fraction,
                            overexposed_fraction=result.overexposed_fraction,
                            uniqueness_score=0.0,
                            perceptual_hash=result.perceptual_hash,
                            face_count=result.face_count,
                            person_count=result.person_count,
                            extra_reasons=[*result.reasons, "duplicate"],
                        )
                        break
                    elif distance <= 8:
                        result = score_image(
                            path=result.path,
                            width=result.width,
                            height=result.height,
                            brightness=result.brightness,
                            sharpness=result.sharpness,
                            underexposed_fraction=result.underexposed_fraction,
                            overexposed_fraction=result.overexposed_fraction,
                            uniqueness_score=25.0,
                            perceptual_hash=result.perceptual_hash,
                            face_count=result.face_count,
                            person_count=result.person_count,
                            extra_reasons=[*result.reasons, "near_duplicate"],
                        )
                        break
                results.append(result)

    return results

