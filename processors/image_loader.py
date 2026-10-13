"""Open any supported photo as an upright RGB Pillow image.

Pillow handles the common formats, and HEIC through pillow-heif. Camera RAW
files go through rawpy (LibRaw) instead. Pillow must not be trusted with
them: it "opens" some RAWs as their tiny embedded thumbnail, or reads a
CR2's undecoded sensor strips as a TIFF, and the analysis would then grade
the wrong picture.
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

try:
    # Lets Pillow open HEIC and HEIF photos, the default format on iPhones.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

try:
    import rawpy
except ImportError:
    rawpy = None

RAW_EXTENSIONS = {
    ".raw",
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".arw",
    ".srf",
    ".sr2",
    ".dng",
    ".orf",
    ".rw2",
    ".raf",
    ".pef",
    ".srw",
    ".x3f",
    ".3fr",
    ".iiq",
    ".erf",
    ".kdc",
    ".mrw",
    ".rwl",
}


def is_raw(path):
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def _raw_error_types():
    if rawpy is None:
        return ()
    return (rawpy.LibRawError,)


def _decode_raw(path, half_size=False):
    """Demosaic a RAW file with the camera's white balance and orientation.

    half_size skips demosaicing and returns half the width and height, which
    is about four times faster. Analysis must not use it, because the blur
    threshold is tuned at full resolution.
    """
    if rawpy is None:
        raise OSError(f"rawpy is not installed, so {Path(path).name} can't be read")
    try:
        with rawpy.imread(str(path)) as raw:
            pixels = raw.postprocess(use_camera_wb=True, output_bps=8, half_size=half_size)
    except _raw_error_types() as error:
        raise OSError(f"Could not decode RAW file {Path(path).name}: {error}") from error
    return Image.fromarray(pixels)


def _embedded_jpeg(path, min_side):
    """Return the camera's embedded JPEG preview if it is at least min_side."""
    if rawpy is None:
        return None
    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
    except (*_raw_error_types(), OSError):
        return None
    if thumb.format != rawpy.ThumbFormat.JPEG:
        return None
    with Image.open(BytesIO(thumb.data)) as preview:
        if max(preview.size) < min_side:
            return None
        # Embedded previews carry their own EXIF orientation.
        return ImageOps.exif_transpose(preview).convert("RGB")


def load_image(path):
    """Open a photo at full resolution, upright, as 8-bit RGB.

    Raises OSError or ValueError if the file can't be read.
    """
    if is_raw(path):
        return _decode_raw(path)
    with Image.open(path) as source_image:
        return ImageOps.exif_transpose(source_image).convert("RGB")


def load_preview_image(path, max_side):
    """Open a photo for display, at least max_side on its longest side if possible.

    For RAW files the camera's embedded JPEG is used when it's big enough,
    since demosaicing just to show a preview is slow.
    """
    if is_raw(path):
        preview = _embedded_jpeg(path, max_side)
        if preview is not None:
            return preview
        return _decode_raw(path, half_size=True)
    with Image.open(path) as source_image:
        return ImageOps.exif_transpose(source_image).convert("RGB")
