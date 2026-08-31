import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFilter

from file_scanner import scan_folder
from processors.image_processor import process_image


class PhotoPipelineTests(unittest.TestCase):
    def test_mixed_fixture_detects_blur_and_duplicate(self):
        results = scan_folder(Path("test_folders/mixed"))
        results_by_name = {result.path.name: result for result in results}

        self.assertIn("blurry_image.jpg", results_by_name)
        self.assertIn("duplicate_image.jpg", results_by_name)
        self.assertIn("blurry", results_by_name["blurry_image.jpg"].reasons)
        self.assertIn("duplicate", results_by_name["duplicate_image.jpg"].reasons)

    def test_mixed_fixture_runs_face_detection(self):
        results = scan_folder(Path("test_folders/mixed"))
        results_by_name = {result.path.name: result for result in results}

        self.assertGreaterEqual(results_by_name["J_MottaBday.jpg"].face_count, 1)
        self.assertIn("contains_face", results_by_name["J_MottaBday.jpg"].reasons)

    def test_mixed_fixture_detects_people_without_requiring_faces(self):
        results = scan_folder(Path("test_folders/mixed"))
        results_by_name = {result.path.name: result for result in results}
        result = results_by_name["IMG_20171223_170953.jpg"]

        self.assertGreaterEqual(result.person_count, 1)
        self.assertIn("contains_person", result.reasons)

    def test_mixed_fixture_identifies_at_least_seven_people_photos(self):
        results = scan_folder(Path("test_folders/mixed"))
        people_photos = [result for result in results if "contains_person" in result.reasons]

        self.assertGreaterEqual(len(people_photos), 7)

    def test_mixed_fixture_ignores_videos(self):
        results = scan_folder(Path("test_folders/mixed"))

        self.assertTrue(results)
        self.assertTrue(all(result.path.suffix.lower() != ".mp4" for result in results))
        self.assertTrue(all(result.path.suffix.lower() != ".mov" for result in results))

    def test_detects_blurry_and_accidental_flat_shots(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            blur_image = Image.new("RGB", (1200, 1200), (180, 180, 180))
            blur_image = blur_image.filter(ImageFilter.GaussianBlur(7))
            blur_path = temp_path / "blurred.jpg"
            blur_image.save(blur_path)

            blur_result = process_image(blur_path)
            self.assertIsNotNone(blur_result)
            self.assertIn("blurry", blur_result.reasons)

            flat_image = Image.new("RGB", (1200, 1200), (128, 128, 128))
            flat_path = temp_path / "flat.jpg"
            flat_image.save(flat_path)

            flat_result = process_image(flat_path)
            self.assertIsNotNone(flat_result)
            self.assertTrue(
                "low_contrast" in flat_result.reasons
                or "accidental_shot" in flat_result.reasons
            )

    def test_detects_significant_scenic_and_low_significance_ground(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            scenic = Image.new("RGB", (1200, 800), (100, 160, 220))
            draw = ImageDraw.Draw(scenic)
            draw.polygon([(0, 550), (280, 280), (520, 470), (820, 220), (1200, 550)], fill=(40, 110, 60))
            draw.rectangle((0, 550, 1200, 800), fill=(80, 150, 80))
            scenic_path = temp_path / "scenic.jpg"
            scenic.save(scenic_path)

            scenic_result = process_image(scenic_path)
            self.assertIsNotNone(scenic_result)
            self.assertGreaterEqual(scenic_result.significance_score, 60)
            self.assertIn("scenic", scenic_result.reasons)

            ground = Image.new("RGB", (1200, 800), (72, 84, 58))
            draw = ImageDraw.Draw(ground)
            draw.rectangle((0, 550, 1200, 800), fill=(60, 75, 45))
            ground_path = temp_path / "ground_only.jpg"
            ground.save(ground_path)

            ground_result = process_image(ground_path)
            self.assertIsNotNone(ground_result)
            self.assertLess(ground_result.significance_score, 35)
            self.assertTrue(
                "low_significance" in ground_result.reasons
                or "ground_only" in ground_result.reasons
            )


if __name__ == "__main__":
    unittest.main()