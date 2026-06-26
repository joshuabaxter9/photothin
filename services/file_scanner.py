from pathlib import Path
from services.image_processor import process_image
from services.video_processor import process_video

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

    #print name, can delete later
    for file in path.iterdir():
        extension = file.suffix.lower()
        if extension in SUPPORTED_IMAGE_EXTENSIONS:
            process_image(file)
        elif extension in SUPPORTED_VIDEO_EXTENSIONS:
            process_video(file)
        else:
            continue
            # ignore unsupported files

        #print file names here
        # print(file.name, extension)

