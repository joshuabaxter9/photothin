import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from analysis.scoring import score_image
from file_scanner import _mark_duplicates, scan_folder
from processors.image_processor import process_image
from processors.video_processor import process_video


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

    def test_mixed_fixture_processes_supported_videos(self):
        results = scan_folder(Path("test_folders/mixed"))
        video_results = [
            result for result in results if result.path.suffix.lower() in {".mp4", ".mov"}
        ]

        self.assertTrue(results)
        self.assertTrue(video_results)
        self.assertIn("VID_20180804_191458.mp4", {result.path.name for result in video_results})

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

    def test_scores_video_by_sampling_frames_according_to_length(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_path = temp_path / "sample_video.mp4"

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (160, 120))
            self.assertTrue(writer.isOpened())

            for _ in range(20):
                frame = 255 * np.ones((120, 160, 3), dtype=np.uint8)
                cv2.rectangle(frame, (20, 20), (140, 100), (0, 128, 255), -1)
                writer.write(frame)
            writer.release()

            result = process_video(video_path)
            self.assertIsNotNone(result)
            self.assertEqual(result.path.name, "sample_video.mp4")
            self.assertGreaterEqual(result.final_score, 0)


    def test_videos_do_not_make_later_images_duplicates(self):
        def make_result(name, perceptual_hash):
            return score_image(
                path=Path(name),
                width=1200,
                height=800,
                brightness=120.0,
                contrast=48.0,
                sharpness=300.0,
                underexposed_fraction=0.0,
                overexposed_fraction=0.0,
                perceptual_hash=perceptual_hash,
            )

        video = make_result("clip.mp4", "")
        photo = make_result("photo.jpg", "01" * 32)
        copy = make_result("copy.jpg", "01" * 32)
        different = make_result("other.jpg", "10" * 32)

        marked = {
            result.path.name: result
            for result in _mark_duplicates([video, photo, copy, different])
        }

        self.assertNotIn("duplicate", marked["photo.jpg"].reasons)
        self.assertIn("duplicate", marked["copy.jpg"].reasons)
        self.assertNotIn("duplicate", marked["other.jpg"].reasons)
        self.assertNotIn("near_duplicate", marked["other.jpg"].reasons)

    def test_faces_lift_a_photo_to_keep_unless_eyes_are_closed(self):
        def score(**faces):
            # Decent but unremarkable on its own: lands in the review band.
            return score_image(
                path=Path("photo.jpg"),
                width=1200,
                height=800,
                brightness=120.0,
                contrast=48.0,
                sharpness=300.0,
                underexposed_fraction=0.0,
                overexposed_fraction=0.0,
                **faces,
            )

        self.assertEqual(score().classification, "REVIEW")
        self.assertEqual(score(face_count=1).classification, "KEEP")
        eyes_closed = score(face_count=1, eyes_closed=True)
        self.assertEqual(eyes_closed.classification, "DISCARD_CANDIDATE")
        self.assertIn("eyes_closed", eyes_closed.reasons)
        self.assertLess(eyes_closed.final_score, score().final_score)

    def test_anything_below_fifty_is_a_discard_candidate(self):
        result = process_image(Path("test_folders/mixed/IMG_20171223_170953.jpg"))
        flat = Image.new("RGB", (1200, 1200), (128, 128, 128))
        with TemporaryDirectory() as temp_dir:
            flat_path = Path(temp_dir) / "flat.jpg"
            flat.save(flat_path)
            flat_result = process_image(flat_path)

        self.assertGreaterEqual(result.final_score, 50)
        self.assertNotEqual(result.classification, "DISCARD_CANDIDATE")
        self.assertLess(flat_result.final_score, 50)
        self.assertEqual(flat_result.classification, "DISCARD_CANDIDATE")

    def test_false_faces_in_fences_are_rejected(self):
        # Haar finds four "faces" here, three of them in a fence. Only the
        # toddler is real.
        result = process_image(Path("test_folders/mixed/IMG_1657.JPG"))
        self.assertEqual(result.face_count, 1)

    def test_squinting_smiles_are_not_eyes_closed(self):
        result = process_image(Path("test_folders/mixed/IMG_20180803_124707.jpg"))
        self.assertEqual(result.face_count, 3)
        self.assertNotIn("eyes_closed", result.reasons)
        self.assertEqual(result.classification, "KEEP")

if __name__ == "__main__":
    unittest.main()