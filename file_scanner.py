import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from processors.image_loader import RAW_EXTENSIONS
from processors.image_processor import process_image
from processors.video_processor import process_video
from analysis.device import gpu_worker_slots
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
    *RAW_EXTENSIONS,
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


def media_kind(file_path):
    """Return "image", "video", or None for an unsupported file."""
    extension = Path(file_path).suffix.lower()
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    if extension in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    return None


def _collect_media(path):
    """List supported files in a stable order, tagged as image or video."""
    media = []
    for file in sorted(path.rglob("*"), key=lambda item: str(item).lower()):
        if not file.is_file():
            continue
        kind = media_kind(file)
        if kind is not None:
            media.append((file, kind))
    return media


def _analyze_media(item):
    file, kind = item
    try:
        if kind == "image":
            return process_image(file)
        return process_video(file)
    except Exception:
        # One unreadable or unusual file should not stop the whole scan.
        return None


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


def iter_analyzed(media, workers=None):
    """Analyze (path, kind) pairs and yield (item, result) in input order.

    Results arrive as soon as each file and every file before it is done, so
    callers can act on early files while later ones are still running. result
    is None when a file could not be analyzed. Closing the generator early
    cancels any files that have not started yet.
    """
    worker_count = _resolve_workers(workers, len(media))
    if worker_count == 1:
        for item in media:
            yield item, _analyze_media(item)
        return

    # Workers beyond what fits in GPU memory run on the CPU, so a small GPU
    # still helps without being overloaded.
    gpu_slots = (multiprocessing.Value("i", 0), gpu_worker_slots(worker_count))
    with TemporaryDirectory(prefix="photothin_workers_") as settings_root:
        pool = ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=init_worker,
            initargs=(settings_root, _ultralytics_settings_file(), gpu_slots),
        )
        try:
            for item, result in zip(media, pool.map(_analyze_media, media)):
                yield item, result
        finally:
            pool.shutdown(wait=True, cancel_futures=True)


def _hash_distance(left_hash, right_hash):
    """Count differing bits between two equal-length strings of 0s and 1s."""
    if len(left_hash) != len(right_hash):
        return sum(left != right for left, right in zip(left_hash, right_hash))
    return (int(left_hash, 2) ^ int(right_hash, 2)).bit_count()


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


def apply_duplicate_check(result, previous_hashes):
    """Rescore result if it matches an earlier image's perceptual hash.

    Videos have no perceptual hash, so they are never compared. Comparing
    against an empty hash would always count as a match.
    """
    if not result.perceptual_hash:
        return result
    for previous_hash in previous_hashes:
        if not previous_hash:
            continue
        distance = _hash_distance(result.perceptual_hash, previous_hash)
        if distance <= 2:
            return _rescore_as_duplicate(result, 0.0, "duplicate")
        if distance <= 8:
            return _rescore_as_duplicate(result, 25.0, "near_duplicate")
    return result


def _mark_duplicates(results):
    """Compare each image with the images before it, in order."""
    marked = []
    for result in results:
        marked.append(
            apply_duplicate_check(result, [previous.perceptual_hash for previous in marked])
        )
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
    analyzed = [result for _, result in iter_analyzed(media, workers) if result is not None]
    return _mark_duplicates(analyzed)
