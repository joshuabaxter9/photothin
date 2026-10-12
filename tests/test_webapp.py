import io
import time
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from webapp.server import create_app
from webapp.storage import clean_relative_path


def jpeg_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def heic_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="HEIF")
    return buffer.getvalue()


def flat_gray_photo():
    # No detail at all: blurry, low contrast, low score. Always needs review.
    return Image.new("RGB", (1200, 900), (128, 128, 128))


def video_bytes(folder):
    path = Path(folder) / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (160, 120))
    for _ in range(20):
        frame = np.full((120, 160, 3), 200, dtype=np.uint8)
        cv2.rectangle(frame, (20, 20), (140, 100), (0, 128, 255), -1)
        writer.write(frame)
    writer.release()
    return path.read_bytes()


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(data_dir=Path(self.temp.name) / "data", workers=1)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def upload(self, session_id, rel_path, content):
        return self.client.post(
            f"/api/sessions/{session_id}/files",
            data={"rel_path": rel_path},
            files={"file": (rel_path.rsplit("/", 1)[-1], content)},
        )

    def upload_id_for(self, session_id, rel_path):
        store = self.app.state.store
        with store._connect() as connection:
            return connection.execute(
                "SELECT id FROM items WHERE session_id = ? AND rel_path = ?",
                (session_id, rel_path),
            ).fetchone()["id"]

    def wait_for_analysis(self, session_id, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.client.get(f"/api/sessions/{session_id}").json()
            if state["session"]["status"] == "ready" and not state["running"]:
                return state
            time.sleep(0.2)
        self.fail("Analysis did not finish in time")

    def test_full_review_flow(self):
        session = self.client.post("/api/sessions", json={"name": "Trip"}).json()
        session_id = session["id"]

        gray = jpeg_bytes(flat_gray_photo())
        self.assertEqual(self.upload(session_id, "day1/gray.jpg", gray).status_code, 201)
        self.assertEqual(self.upload(session_id, "day2/gray copy.heic", heic_bytes(flat_gray_photo())).status_code, 201)
        self.assertEqual(self.upload(session_id, "clip.mp4", video_bytes(self.temp.name)).status_code, 201)
        self.assertEqual(self.upload(session_id, "notes.txt", b"hello").status_code, 415)

        self.assertEqual(self.client.post(f"/api/sessions/{session_id}/analyze").status_code, 202)
        state = self.wait_for_analysis(session_id)

        # The video is kept automatically. Both photos wait for review,
        # including the HEIC one, and the HEIC is flagged as a duplicate.
        self.assertEqual(state["counts"]["total"], 3)
        self.assertEqual(state["counts"]["auto_kept"], 1)
        queue = {item["rel_path"]: item for item in state["queue"]}
        self.assertEqual(set(queue), {"day1/gray.jpg", "day2/gray copy.heic"})
        self.assertIn("duplicate", queue["day2/gray copy.heic"]["reasons"])
        self.assertFalse(state["finished"])

        folders = {name: Path(path) for name, path in state["folders"].items()}
        self.assertTrue((folders["approved"] / "clip.mp4").is_file())

        # HEIC photos get a JPEG preview the browser can show.
        heic_id = queue["day2/gray copy.heic"]["id"]
        preview = self.client.get(f"/api/items/{heic_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")
        self.assertEqual(Image.open(io.BytesIO(preview.content)).format, "JPEG")

        # Discard moves the file, undo puts it back in the queue.
        self.client.post(f"/api/items/{heic_id}/decision", json={"decision": "discard"})
        self.assertTrue((folders["discarded"] / "day2/gray copy.heic").is_file())
        self.assertFalse((folders["incoming"] / "day2/gray copy.heic").exists())

        undone = self.client.post(f"/api/sessions/{session_id}/undo").json()
        self.assertEqual(undone["id"], heic_id)
        self.assertTrue((folders["incoming"] / "day2/gray copy.heic").is_file())
        state = self.client.get(f"/api/sessions/{session_id}").json()
        self.assertEqual(len(state["queue"]), 2)

        # Decide both, then the session is finished.
        gray_id = queue["day1/gray.jpg"]["id"]
        self.client.post(f"/api/items/{gray_id}/decision", json={"decision": "keep"})
        self.client.post(f"/api/items/{heic_id}/decision", json={"decision": "discard"})
        state = self.client.get(f"/api/sessions/{session_id}").json()
        self.assertTrue(state["finished"])
        self.assertEqual(state["counts"]["approved"], 2)
        self.assertEqual(state["counts"]["discarded"], 1)

        approved_zip = self.client.get(f"/api/sessions/{session_id}/download/approved")
        self.assertEqual(approved_zip.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(approved_zip.content)) as archive:
            self.assertEqual(sorted(archive.namelist()), ["clip.mp4", "day1/gray.jpg"])
            self.assertEqual(archive.read("day1/gray.jpg"), gray)

        discarded_zip = self.client.get(f"/api/sessions/{session_id}/download/discarded")
        with zipfile.ZipFile(io.BytesIO(discarded_zip.content)) as archive:
            self.assertEqual(archive.namelist(), ["day2/gray copy.heic"])

        self.assertEqual(self.client.get(f"/api/sessions/{session_id}/download/incoming").status_code, 409)

        # Deleting removes the session folder.
        session_folder = folders["approved"].parent
        self.assertEqual(self.client.delete(f"/api/sessions/{session_id}").status_code, 204)
        self.assertFalse(session_folder.exists())
        self.assertEqual(self.client.get(f"/api/sessions/{session_id}").status_code, 404)

    def test_auto_kept_files_cannot_be_reviewed(self):
        session_id = self.client.post("/api/sessions", json={"name": "Clips"}).json()["id"]
        self.upload(session_id, "clip.mp4", video_bytes(self.temp.name))
        self.client.post(f"/api/sessions/{session_id}/analyze")
        state = self.wait_for_analysis(session_id)
        self.assertTrue(state["finished"])

        self.assertEqual(state["counts"]["approved"], 1)
        video_id = self.upload_id_for(session_id, "clip.mp4")
        response = self.client.post(f"/api/items/{video_id}/decision", json={"decision": "discard"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(f"/api/sessions/{session_id}/download/discarded").status_code, 409)

    def test_exact_copies_are_discarded_automatically(self):
        session_id = self.client.post("/api/sessions", json={"name": "Copies"}).json()["id"]
        photo = jpeg_bytes(flat_gray_photo())
        different = jpeg_bytes(Image.new("RGB", (1200, 900), (90, 120, 160)))
        # Alphabetically the copies sort before the original, because a
        # space sorts before a period. The original must still be kept.
        self.upload(session_id, "IMG_1 - Copy.jpg", photo)
        self.upload(session_id, "IMG_1.jpg", photo)
        self.upload(session_id, "sub/IMG_1 (1).jpg", photo)
        self.upload(session_id, "other.jpg", different)

        self.client.post(f"/api/sessions/{session_id}/analyze")
        state = self.wait_for_analysis(session_id)

        self.assertEqual({item["rel_path"] for item in state["queue"]}, {"IMG_1.jpg", "other.jpg"})
        self.assertEqual(state["counts"]["exact_duplicates"], 2)
        self.assertEqual(state["counts"]["discarded"], 2)
        self.assertEqual(state["counts"]["auto_kept"], 0)

        discarded = Path(state["folders"]["discarded"])
        self.assertTrue((discarded / "IMG_1 - Copy.jpg").is_file())
        self.assertTrue((discarded / "sub/IMG_1 (1).jpg").is_file())
        self.assertTrue((Path(state["folders"]["incoming"]) / "IMG_1.jpg").is_file())

        store = self.app.state.store
        kept_id = self.upload_id_for(session_id, "IMG_1.jpg")
        copy = store.get_item(self.upload_id_for(session_id, "IMG_1 - Copy.jpg"))
        self.assertEqual(copy["duplicate_of"], kept_id)
        self.assertEqual(copy["decided_by"], "auto")
        self.assertEqual(store.item_summary(copy)["reasons"], ["exact_duplicate"])

        # Automatic discards are not part of the user's undo history, and
        # cannot be reviewed.
        self.assertEqual(self.client.post(f"/api/sessions/{session_id}/undo").status_code, 409)
        response = self.client.post(f"/api/items/{copy['id']}/decision", json={"decision": "keep"})
        self.assertEqual(response.status_code, 409)

    def test_old_databases_get_new_columns(self):
        import sqlite3

        data_dir = Path(self.temp.name) / "old"
        data_dir.mkdir()
        connection = sqlite3.connect(data_dir / "photothin.db")
        connection.executescript(
            """
            CREATE TABLE sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL,
                created_at TEXT NOT NULL, status TEXT NOT NULL, error TEXT);
            CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                rel_path TEXT NOT NULL, kind TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                seq INTEGER, analysis TEXT NOT NULL DEFAULT 'pending', classification TEXT,
                final_score REAL, reasons TEXT, perceptual_hash TEXT, width INTEGER,
                height INTEGER, face_count INTEGER, person_count INTEGER, decision TEXT,
                decided_by TEXT, decided_at TEXT, location TEXT NOT NULL DEFAULT 'incoming',
                UNIQUE (session_id, rel_path));
            """
        )
        connection.close()

        app = create_app(data_dir=data_dir, workers=1)
        with app.state.store._connect() as upgraded:
            columns = {row["name"] for row in upgraded.execute("PRAGMA table_info(items)")}
        self.assertIn("content_hash", columns)
        self.assertIn("duplicate_of", columns)

    def test_uploads_close_once_analysis_starts(self):
        session_id = self.client.post("/api/sessions", json={"name": "Late"}).json()["id"]
        self.client.post(f"/api/sessions/{session_id}/analyze")
        self.wait_for_analysis(session_id)
        response = self.upload(session_id, "late.jpg", jpeg_bytes(flat_gray_photo()))
        self.assertEqual(response.status_code, 409)

    def test_restart_marks_running_sessions_as_interrupted(self):
        store = self.app.state.store
        session_id = store.create_session("Paused")
        store.set_status(session_id, "analyzing")
        restarted = create_app(data_dir=store.data_dir, workers=1)
        self.assertEqual(restarted.state.store.get_session(session_id)["status"], "interrupted")


class CleanRelativePathTests(unittest.TestCase):
    def test_keeps_normal_paths(self):
        self.assertEqual(clean_relative_path("Trip/day 1/IMG_1.jpg"), "Trip/day 1/IMG_1.jpg")
        self.assertEqual(clean_relative_path("Trip\\day1\\a.jpg"), "Trip/day1/a.jpg")
        self.assertEqual(clean_relative_path("/./a.jpg"), "a.jpg")

    def test_rejects_escaping_paths(self):
        for bad in ["../a.jpg", "a/../../b.jpg", "", "/", "./"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    clean_relative_path(bad)

    def test_replaces_characters_windows_rejects(self):
        self.assertEqual(clean_relative_path('C:/what?.jpg'), "C_/what_.jpg")


if __name__ == "__main__":
    unittest.main()
