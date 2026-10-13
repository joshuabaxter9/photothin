"""Browser-friendly JPEG previews of photos.

Browsers cannot show HEIC or camera RAW photos, and full-size phone photos
make the review screen slow. Each photo under review gets a JPEG preview,
made once and cached next to the session.
"""

import os
import tempfile

from PIL import Image

from processors.image_loader import load_preview_image

PREVIEW_MAX_SIDE = 1600
PREVIEW_QUALITY = 85


def ensure_preview(source_path, preview_path, max_side=PREVIEW_MAX_SIDE):
    """Create the preview if it does not exist yet, and return its path."""
    if preview_path.exists():
        return preview_path
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    image = load_preview_image(source_path, max_side)
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    # Two requests for the same preview can race. Each writes its own
    # temporary file, and the rename makes the final file appear whole.
    handle, temp_name = tempfile.mkstemp(dir=preview_path.parent, suffix=".jpg")
    try:
        with os.fdopen(handle, "wb") as temp_file:
            image.save(temp_file, format="JPEG", quality=PREVIEW_QUALITY, optimize=True)
        os.replace(temp_name, preview_path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise
    return preview_path
