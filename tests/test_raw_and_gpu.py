import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np
from PIL import Image

from analysis import pixel_stats
from processors.image_loader import is_raw, load_image
from processors.image_processor import process_image
from worker_setup import _claim_device

try:
    import torch

    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False


def _textured_pixels(height=900, width=1200):
    generator = np.random.default_rng(7)
    pixels = generator.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    # Pixels exactly on the exposure thresholds, where rounding matters.
    pixels[:50] = 10
    pixels[50:100] = 245
    return pixels


class RawLoadingTests(unittest.TestCase):
    def test_raw_extensions_are_recognised_in_any_case(self):
        self.assertTrue(is_raw("photo.CR2"))
        self.assertTrue(is_raw("photo.nef"))
        self.assertFalse(is_raw("photo.jpg"))

    def test_raw_files_are_never_handed_to_pillow(self):
        # Pillow would open this as a TIFF, the way it misreads some real
        # RAWs, and the analysis would grade the wrong picture.
        with TemporaryDirectory() as temp_dir:
            fake_raw = Path(temp_dir) / "not_really.nef"
            Image.new("RGB", (64, 48), (90, 120, 150)).save(fake_raw, format="TIFF")

            with self.assertRaises(OSError):
                load_image(fake_raw)
            self.assertIsNone(process_image(fake_raw))


class PixelStatsTests(unittest.TestCase):
    @unittest.skipUnless(CUDA_AVAILABLE, "needs a CUDA GPU and the CUDA build of PyTorch")
    def test_gpu_and_cpu_measurements_agree(self):
        pixels = _textured_pixels()
        cpu = pixel_stats._measure_numpy(pixels)
        gpu = pixel_stats._measure_torch(pixels)

        # Threshold counts must match exactly, not just closely.
        self.assertEqual(cpu.underexposed_fraction, gpu.underexposed_fraction)
        self.assertEqual(cpu.overexposed_fraction, gpu.overexposed_fraction)
        for name, cpu_value in vars(cpu).items():
            self.assertAlmostEqual(cpu_value, getattr(gpu, name), delta=abs(cpu_value) * 1e-5)
        self.assertEqual(
            pixel_stats.compute_significance(cpu), pixel_stats.compute_significance(gpu)
        )

    def test_gpu_failure_falls_back_to_cpu(self):
        pixels = _textured_pixels(120, 160)
        with mock.patch.object(pixel_stats, "use_gpu", return_value=True), mock.patch.object(
            pixel_stats, "_measure_torch", side_effect=RuntimeError("CUDA out of memory")
        ):
            stats = pixel_stats.measure_pixels(pixels)

        self.assertEqual(stats, pixel_stats._measure_numpy(pixels))


class WorkerDeviceTests(unittest.TestCase):
    def test_workers_beyond_the_gpu_slots_use_the_cpu(self):
        import multiprocessing

        counter = multiprocessing.Value("i", 0)
        devices = []
        for _ in range(3):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PHOTOTHIN_DEVICE", None)
                _claim_device((counter, 2))
                devices.append(os.environ.get("PHOTOTHIN_DEVICE", "auto"))

        self.assertEqual(devices, ["auto", "auto", "cpu"])


if __name__ == "__main__":
    unittest.main()
