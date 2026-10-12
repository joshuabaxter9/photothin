"""Setup for the worker processes that scan_folder starts.

This module must not import the rest of the project. The worker runs it
before importing ultralytics, which rewrites its settings file on every
import. If many workers import ultralytics at once, one can read the file
while another is halfway through writing it, which corrupts it. Giving each
worker its own settings folder avoids that.
"""

import multiprocessing
import multiprocessing.connection
import os
import shutil
import threading
from pathlib import Path


def _exit_when_parent_dies():
    """Stop this worker if the process that started it goes away.

    Normally the pool shuts its workers down. If the parent crashes or is
    killed, the workers would otherwise keep running with nothing to report
    to.
    """
    parent = multiprocessing.parent_process()
    if parent is None:
        return

    def watch():
        multiprocessing.connection.wait([parent.sentinel])
        os._exit(1)

    threading.Thread(target=watch, name="parent-watchdog", daemon=True).start()


def init_worker(settings_root, settings_file):
    _exit_when_parent_dies()

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
