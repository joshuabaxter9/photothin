import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from processors.image_processor import process_image
from processors.video_processor import process_video
from analysis.scoring import score_image
from worker_setup import init_worker

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

# Each worker process loads its own copy of PyTorch and the YOLO model, so
# the default is half the logical cores, capped. On an i9-12900K, 8 workers
# beat 6, 10, 12 and 16 on a 105-file test folder.
MAX_DEFAULT_WORKERS = 8


def _collect_media(path):
    """List supported files in a stable order, tagged as image or video."""
    media = []
    for file in sorted(path.rglob("*"), key=lambda item: str(item).lower()):
        if not file.is_file():
            continue
        extension = file.suffix.lower()
        if extension in SUPPORTED_IMAGE_EXTENSIONS:
            media.append((file, "image"))
        elif extension in SUPPORTED_VIDEO_EXTENSIONS:
            media.append((file, "video"))
    return media


def _analyze_media(item):
    file, kind = item
    if kind == "image":
        return process_image(file)
    return process_video(file)


def _ultralytics_settings_file():
    try:
        from ultralytics.utils import SETTINGS_FILE
    except ImportError:
        return None
    return str(SETTINGS_FILE)


def _resolve_workers(workers, file_count):
    if workers is None:
        workers = min(MAX_DEFAULT_WORKERS, (os.cpu_count() or 2) // 2)
    return max(1, min(workers, file_count))


def _hash_distance(left_hash, right_hash):
    return sum(left != right for left, right in zip(left_hash, right_hash))


def _rescore_as_duplicate(result, uniqueness_score, reason):
    return score_image(
        path=result.path,
        width=result.width,
        height=result.height,
        brightness=result.brightness,
        contrast=result.contrast,
        significance_score=result.significance_score,
        sharpness=result.sharpness,
        underexposed_fraction=result.underexposed_fraction,
        overexposed_fraction=result.overexposed_fraction,
        uniqueness_score=uniqueness_score,
        perceptual_hash=result.perceptual_hash,
        face_count=result.face_count,
        person_count=result.person_count,
        extra_reasons=[*result.reasons, reason],
    )


def _mark_duplicates(results):
    """Compare each image with the images before it, after all analysis is done.

    Videos have no perceptual hash, so they are skipped. Comparing against an
    empty hash would always count as a match.
    """
    marked = []
    for result in results:
        if result.perceptual_hash:
            for previous_result in marked:
                if not previous_result.perceptual_hash:
                    continue
                distance = _hash_distance(
                    result.perceptual_hash, previous_result.perceptual_hash
                )
                if distance <= 2:
                    result = _rescore_as_duplicate(result, 0.0, "duplicate")
                    break
                if distance <= 8:
                    result = _rescore_as_duplicate(result, 25.0, "near_duplicate")
                    break
        marked.append(result)
    return marked


def scan_folder(folder_path, workers=None):
    """Analyze every supported photo and video in a folder.

    workers sets how many processes analyze files in parallel. None picks a
    default from the CPU count, and 1 runs everything in this process.
    """
    path = Path(folder_path)

    if not path.exists():
        print("Path does not exist")
        return []

    if not path.is_dir():
        print("Path is not a folder")
        return []

    media = _collect_media(path)
    if not media:
        return []

    worker_count = _resolve_workers(workers, len(media))
    if worker_count == 1:
        analyzed = [_analyze_media(item) for item in media]
    else:
        with TemporaryDirectory(prefix="photothin_workers_") as settings_root:
            with ProcessPoolExecutor(
                max_workers=worker_count,
                initializer=init_worker,
                initargs=(settings_root, _ultralytics_settings_file()),
            ) as pool:
                analyzed = list(pool.map(_analyze_media, media))

    return _mark_duplicates([result for result in analyzed if result is not None])
