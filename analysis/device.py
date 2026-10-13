"""Choose whether analysis runs on an NVIDIA GPU or the CPU.

The PHOTOTHIN_DEVICE environment variable picks the device:

- "auto" (the default) uses the GPU when PyTorch can see one, else the CPU.
- "cuda" or "cpu" forces one. "cuda" falls back to the CPU, with a warning,
  when no GPU is usable.

PyTorch is imported lazily, the first time the device is asked for, so that
worker processes import it only after worker_setup has run.
"""

import os
import warnings

DEVICE_ENV_VAR = "PHOTOTHIN_DEVICE"

# Each process on the GPU may hold at most this much for images. The pixel
# measurements peak near 11 bytes per pixel, so this covers photos up to
# about 70 megapixels; a bigger one runs out of room and falls back to the
# CPU. Without a cap, Windows quietly spills GPU memory into system RAM once
# it's full, and every worker on the GPU slows to a crawl.
GPU_TENSOR_BUDGET_MB = 768
# What one GPU worker is assumed to need in all: the budget above plus the
# CUDA context and the YOLO model.
GPU_WORKER_MB = 1024
# Left free for the display and other programs.
GPU_RESERVE_MB = 512

_device = None


def _detect_device():
    requested = os.environ.get(DEVICE_ENV_VAR, "auto").strip().lower()
    if requested == "cpu":
        return "cpu"

    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    if cuda_available:
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(
            min(1.0, GPU_TENSOR_BUDGET_MB * 2**20 / total)
        )
        return "cuda"
    if requested == "cuda":
        warnings.warn(
            f"{DEVICE_ENV_VAR}=cuda but no CUDA GPU is usable; running on the CPU. "
            "The PyTorch build from the default package index is CPU-only on Windows."
        )
    return "cpu"


def get_device():
    """Return "cuda" or "cpu", decided once per process."""
    global _device
    if _device is None:
        _device = _detect_device()
    return _device


def use_gpu():
    return get_device() == "cuda"


def gpu_worker_slots(worker_count):
    """How many of worker_count worker processes should use the GPU.

    The rest run on the CPU. This is decided from the GPU memory free when
    the scan starts. It returns 0 when the GPU is off or unusable.
    """
    if os.environ.get(DEVICE_ENV_VAR, "auto").strip().lower() == "cpu":
        return 0
    try:
        import torch

        if not torch.cuda.is_available():
            return 0
        free_bytes, _ = torch.cuda.mem_get_info()
    except (ImportError, RuntimeError):
        return 0
    free_mb = free_bytes // 2**20
    return max(0, min(worker_count, (free_mb - GPU_RESERVE_MB) // GPU_WORKER_MB))
