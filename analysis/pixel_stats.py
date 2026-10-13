"""Full-resolution pixel measurements shared by photos and video frames.

Sharpness, significance and exposure stay at full resolution on purpose: the
sharpness metric changes a lot with image size, so the blur threshold only
holds at the original resolution.

The same math runs in NumPy on the CPU or in PyTorch on a CUDA GPU, whichever
analysis.device picks. Both use float32 grayscale. Their results agree to
about six significant figures; reductions on the GPU add in a different
order, so the last digits can differ.
"""

import warnings
from dataclasses import dataclass

import numpy as np

from analysis.device import use_gpu

# Luma weights for grayscale conversion.
_RED_WEIGHT, _GREEN_WEIGHT, _BLUE_WEIGHT = 0.299, 0.587, 0.114


@dataclass
class PixelStats:
    brightness: float
    contrast: float
    sharpness: float
    underexposed_fraction: float
    overexposed_fraction: float
    # Inputs to the significance heuristic. The image is split into an upper
    # two thirds and a lower third, roughly sky or scene versus ground.
    upper_mean: float
    upper_std: float
    lower_mean: float
    lower_std: float
    edge_density: float


def to_grayscale(rgb_pixels):
    """Luma grayscale as float32."""
    return (
        rgb_pixels[:, :, 0].astype(np.float32) * _RED_WEIGHT
        + rgb_pixels[:, :, 1].astype(np.float32) * _GREEN_WEIGHT
        + rgb_pixels[:, :, 2].astype(np.float32) * _BLUE_WEIGHT
    )


def _measure_numpy(rgb_pixels):
    grayscale = to_grayscale(rgb_pixels)
    split = grayscale.shape[0] * 2 // 3
    upper_region = grayscale[:split]
    lower_region = grayscale[split:]
    vertical_diff = np.diff(grayscale, axis=0)
    horizontal_diff = np.diff(grayscale, axis=1)
    return PixelStats(
        brightness=float(grayscale.mean()),
        contrast=float(grayscale.std()),
        sharpness=float(np.var(vertical_diff) + np.var(horizontal_diff)),
        underexposed_fraction=float((grayscale <= 10).mean()),
        overexposed_fraction=float((grayscale >= 245).mean()),
        upper_mean=float(upper_region.mean()),
        upper_std=float(upper_region.std()),
        lower_mean=float(lower_region.mean()),
        lower_std=float(lower_region.std()),
        edge_density=float(np.abs(vertical_diff).mean() + np.abs(horizontal_diff).mean()),
    )


def _measure_torch(rgb_pixels):
    import torch

    # Several worker processes share one GPU, so this keeps memory low: the
    # upload stays 8-bit, the grayscale is built in place, and each
    # difference image is dropped as soon as it has been measured. A photo
    # peaks at about 11 bytes per pixel.
    with torch.inference_mode():
        # Arrays from Pillow are read-only, and PyTorch warns about that even
        # though nothing here writes to them.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            host_pixels = torch.from_numpy(np.ascontiguousarray(rgb_pixels))
        pixels = host_pixels.to("cuda")
        # Multiply and add as separate steps, rounding the way NumPy does. A
        # fused multiply-add rounds differently, and pixels sitting exactly on
        # the exposure thresholds would then be counted differently.
        grayscale = pixels[:, :, 0].to(torch.float32).mul_(_RED_WEIGHT)
        grayscale.add_(pixels[:, :, 1].to(torch.float32).mul_(_GREEN_WEIGHT))
        grayscale.add_(pixels[:, :, 2].to(torch.float32).mul_(_BLUE_WEIGHT))
        del pixels

        split = grayscale.shape[0] * 2 // 3
        upper_region = grayscale[:split]
        lower_region = grayscale[split:]
        values = [
            grayscale.mean(),
            grayscale.std(correction=0),
            # Exact counts, so the fractions match NumPy's to the last digit.
            torch.count_nonzero(grayscale <= 10).double() / grayscale.numel(),
            torch.count_nonzero(grayscale >= 245).double() / grayscale.numel(),
            upper_region.mean(),
            upper_region.std(correction=0),
            lower_region.mean(),
            lower_region.std(correction=0),
        ]
        sharpness = 0
        edge_density = 0
        for dim in (0, 1):
            difference = torch.diff(grayscale, dim=dim)
            sharpness = sharpness + difference.var(correction=0)
            edge_density = edge_density + difference.abs_().mean()
            del difference
        # Collect every value into one tensor so the GPU syncs only once.
        (
            brightness, contrast, underexposed, overexposed,
            upper_mean, upper_std, lower_mean, lower_std,
            sharpness, edge_density,
        ) = torch.stack(
            [value.double() for value in (*values, sharpness, edge_density)]
        ).tolist()
    return PixelStats(
        brightness=brightness,
        contrast=contrast,
        sharpness=sharpness,
        underexposed_fraction=underexposed,
        overexposed_fraction=overexposed,
        upper_mean=upper_mean,
        upper_std=upper_std,
        lower_mean=lower_mean,
        lower_std=lower_std,
        edge_density=edge_density,
    )


def measure_pixels(rgb_pixels):
    """Measure an RGB uint8 array of shape (height, width, 3)."""
    if use_gpu():
        import torch

        try:
            return _measure_torch(rgb_pixels)
        except RuntimeError:
            # Out of GPU memory or a driver problem: this image still gets
            # measured, on the CPU.
            pass
        finally:
            # Hand the memory back. Photos come in different sizes, and a
            # cache that keeps the largest one would crowd out the other
            # workers on the GPU.
            torch.cuda.empty_cache()
    return _measure_numpy(rgb_pixels)


def compute_significance(stats):
    """Score 0 to 100 for whether there is anything worth looking at.

    Returns the score and two lists of reason tags: ["scenic"] for a high
    score, and ["low_significance", "ground_only"] for a low one.
    """
    global_std = stats.contrast
    upper_std = stats.upper_std
    lower_std = stats.lower_std
    horizon_contrast = abs(stats.upper_mean - stats.lower_mean)

    score = 0.0
    if global_std > 18:
        score += 25.0
    if upper_std > 15:
        score += 20.0
    if lower_std > 10:
        score += 15.0
    if stats.edge_density > 2.0:
        score += 20.0
    if horizon_contrast > 10:
        score += 15.0
    if upper_std > 25 and lower_std > 15:
        score += 15.0

    if upper_std < 12 and lower_std < 10 and global_std < 10:
        score -= 45.0
    if stats.lower_mean > 150 and stats.upper_mean < 170 and lower_std < 18:
        score -= 20.0

    score = max(0.0, min(100.0, score))
    return score, (
        ["scenic"] if score >= 60 else [],
        ["low_significance", "ground_only"] if score <= 35 else [],
    )
