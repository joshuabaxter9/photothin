"""Setup for the worker processes that scan_folder starts.

This module must not import the rest of the project. The worker runs it
before importing ultralytics, which rewrites its settings file on every
import. If many workers import ultralytics at once, one can read the file
while another is halfway through writing it, which corrupts it. Giving each
worker its own settings folder avoids that.
"""

import os
import shutil
from pathlib import Path


def init_worker(settings_root, settings_file):
    worker_dir = Path(settings_root) / str(os.getpid())
    worker_dir.mkdir(parents=True, exist_ok=True)
    if settings_file and Path(settings_file).is_file():
        shutil.copyfile(settings_file, worker_dir / Path(settings_file).name)
    os.environ["YOLO_CONFIG_DIR"] = str(worker_dir)

    # One thread per worker, so parallel workers don't compete for cores.
    try:
        import cv2

        cv2.setNumThreads(1)
    except ImportError:
        pass
    try:
        import torch

        torch.set_num_threads(1)
    except ImportError:
        pass
