import unittest
from pathlib import Path

from file_scanner import scan_folder


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


if __name__ == "__main__":
    unittest.main()