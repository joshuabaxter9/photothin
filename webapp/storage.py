"""Session storage for the review web app.

Each review session gets a folder on disk with three subfolders:

    incoming/   uploaded files that have no decision yet
    approved/   files that were kept, automatically or by the user
    discarded/  files the user chose to discard

Nothing is ever deleted during review. A decision moves the file between
these folders, so the folders always match the decisions.

Decisions and analysis results live in an SQLite database. The items table
holds each file's current state, and the decision_log table keeps every
decision in order. The log is what makes undo work, and it gives a record of
who decided what and when. Because everything is on disk, a session survives
closing the browser or restarting the server.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

INCOMING = "incoming"
APPROVED = "approved"
DISCARDED = "discarded"
BUCKETS = (INCOMING, APPROVED, DISCARDED)
DOWNLOADABLE_BUCKETS = (APPROVED, DISCARDED)

KEEP = "keep"
DISCARD = "discard"
DECISION_TO_BUCKET = {KEEP: APPROVED, DISCARD: DISCARDED}

# Reason added to files the analysis could not read. They are kept, because
# nothing should be discarded without the user seeing it.
COULD_NOT_ANALYZE = "could_not_analyze"

# Reason added to a file that is byte-for-byte identical to another file in
# the same session. It is discarded automatically, without being analyzed.
EXACT_DUPLICATE = "exact_duplicate"

HASH_CHUNK_BYTES = 1024 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL,  -- uploading, analyzing, ready, interrupted
    error       TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rel_path        TEXT NOT NULL,
    kind            TEXT NOT NULL,              -- image, video
    size_bytes      INTEGER NOT NULL,
    seq             INTEGER,                    -- analysis order
    analysis        TEXT NOT NULL DEFAULT 'pending',  -- pending, done, failed
    classification  TEXT,
    final_score     REAL,
    reasons         TEXT,                       -- JSON list
    perceptual_hash TEXT,
    width           INTEGER,
    height          INTEGER,
    face_count      INTEGER,
    person_count    INTEGER,
    decision        TEXT,                       -- NULL, keep, discard
    decided_by      TEXT,                       -- auto, user
    decided_at      TEXT,
    location        TEXT NOT NULL DEFAULT 'incoming',
    content_hash    TEXT,                       -- SHA-256 of the file's bytes
    duplicate_of    INTEGER,                    -- the kept copy, for exact duplicates
    UNIQUE (session_id, rel_path)
);

CREATE INDEX IF NOT EXISTS idx_items_session_seq ON items (session_id, seq);

CREATE TABLE IF NOT EXISTS decision_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    decision    TEXT NOT NULL,                  -- keep, discard
    decided_by  TEXT NOT NULL,                  -- auto, user
    created_at  TEXT NOT NULL,
    undone      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_decision_log_session ON decision_log (session_id, id);
"""

_INVALID_NAME_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


class StorageError(Exception):
    """A request that conflicts with the session's current state."""


class NotFound(StorageError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_relative_path(raw_path):
    """Turn an uploaded file's relative path into a safe path inside a folder.

    Rejects anything that could escape the session folder, such as "..",
    and replaces characters Windows does not allow in file names.
    """
    parts = []
    for part in re.split(r"[\\/]+", raw_path or ""):
        part = part.strip()
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("Relative paths may not contain '..'")
        part = _INVALID_NAME_CHARS.sub("_", part).rstrip(". ")
        if not part:
            raise ValueError("Path contains an empty name")
        parts.append(part)
    if not parts:
        raise ValueError("Path is empty")
    return "/".join(parts)


class Store:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "photothin.db"
        # One lock for every write, so a file move and its database update
        # always happen together.
        self._write_lock = threading.RLock()

        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
            # Databases made before a column existed get it added here.
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(items)")
            }
            for column, column_type in (("content_hash", "TEXT"), ("duplicate_of", "INTEGER")):
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE items ADD COLUMN {column} {column_type}")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_session_hash ON items (session_id, content_hash)"
            )
            # Work that was running when the server stopped cannot continue
            # on its own. Mark it so the app offers to resume it.
            connection.execute(
                "UPDATE sessions SET status = 'interrupted' "
                "WHERE status IN ('uploading', 'analyzing')"
            )

    # ----- connections and paths -------------------------------------------

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def session_dir(self, session_id):
        return self.sessions_dir / session_id

    def bucket_dir(self, session_id, bucket):
        if bucket not in BUCKETS:
            raise ValueError(f"Unknown folder: {bucket}")
        return self.session_dir(session_id) / bucket

    def item_file_path(self, item):
        return self.bucket_dir(item["session_id"], item["location"]) / item["rel_path"]

    def preview_path(self, item):
        return self.session_dir(item["session_id"]) / "previews" / f"{item['id']}.jpg"

    # ----- sessions ----------------------------------------------------------

    def create_session(self, name):
        session_id = uuid.uuid4().hex[:12]
        clean_name = (name or "").strip()[:120] or "Untitled folder"
        for bucket in BUCKETS:
            self.bucket_dir(session_id, bucket).mkdir(parents=True, exist_ok=True)
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions (id, name, created_at, status) VALUES (?, ?, ?, 'uploading')",
                (session_id, clean_name, _now()),
            )
        return session_id

    def get_session(self, session_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise NotFound("Session not found")
        return dict(row)

    def set_status(self, session_id, status, error=None):
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET status = ?, error = ? WHERE id = ?",
                (status, error, session_id),
            )

    def list_sessions(self):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*,
                       COUNT(i.id) AS total,
                       SUM(i.analysis != 'pending') AS analyzed,
                       SUM(i.decision = 'keep') AS approved,
                       SUM(i.decision = 'discard') AS discarded,
                       SUM(i.analysis = 'done' AND i.kind = 'image'
                           AND i.decision IS NULL) AS waiting
                FROM sessions s LEFT JOIN items i ON i.session_id = s.id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                """
            ).fetchall()
        return [
            {key: (row[key] or 0) if key in ("total", "analyzed", "approved", "discarded", "waiting") else row[key]
             for key in row.keys()}
            for row in rows
        ]

    def delete_session(self, session_id):
        self.get_session(session_id)
        with self._write_lock:
            with self._connect() as connection:
                connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            shutil.rmtree(self.session_dir(session_id), ignore_errors=True)

    # ----- uploads -----------------------------------------------------------

    def add_upload(self, session_id, raw_rel_path, kind, source_file):
        """Save one uploaded file into incoming/ and register it."""
        session = self.get_session(session_id)
        if session["status"] != "uploading":
            raise StorageError("This session is no longer accepting uploads")
        rel_path = clean_relative_path(raw_rel_path)
        target = self.bucket_dir(session_id, INCOMING) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary name first, so a failed upload never leaves a
        # half-written file under the real name.
        handle, temp_name = tempfile.mkstemp(dir=target.parent, suffix=".part")
        try:
            digest = hashlib.sha256()
            with os.fdopen(handle, "wb") as temp_file:
                while chunk := source_file.read(HASH_CHUNK_BYTES):
                    digest.update(chunk)
                    temp_file.write(chunk)
            content_hash = digest.hexdigest()
            size_bytes = os.path.getsize(temp_name)
            with self._write_lock:
                os.replace(temp_name, target)
                with self._connect() as connection:
                    connection.execute(
                        """
                        INSERT INTO items (session_id, rel_path, kind, size_bytes, content_hash)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT (session_id, rel_path)
                        DO UPDATE SET kind = excluded.kind, size_bytes = excluded.size_bytes,
                                      content_hash = excluded.content_hash
                        """,
                        (session_id, rel_path, kind, size_bytes, content_hash),
                    )
                    item_id = connection.execute(
                        "SELECT id FROM items WHERE session_id = ? AND rel_path = ?",
                        (session_id, rel_path),
                    ).fetchone()["id"]
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return {"id": item_id, "rel_path": rel_path, "size_bytes": size_bytes}

    # ----- analysis ----------------------------------------------------------

    def begin_analysis(self, session_id):
        """Mark the session as analyzing and return the work still to do.

        Returns the pending items in analysis order, plus the perceptual
        hashes of images already analyzed, so duplicate detection still sees
        them when an interrupted session resumes.
        """
        self.get_session(session_id)
        with self._write_lock, self._connect() as connection:
            unordered = connection.execute(
                "SELECT id, rel_path FROM items WHERE session_id = ? AND seq IS NULL",
                (session_id,),
            ).fetchall()
            next_seq = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM items WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            for offset, row in enumerate(
                sorted(unordered, key=lambda row: row["rel_path"].lower()), start=1
            ):
                connection.execute(
                    "UPDATE items SET seq = ? WHERE id = ?", (next_seq + offset, row["id"])
                )
            connection.execute(
                "UPDATE sessions SET status = 'analyzing', error = NULL WHERE id = ?",
                (session_id,),
            )

        self._discard_exact_copies(session_id)

        with self._write_lock, self._connect() as connection:
            pending = connection.execute(
                "SELECT * FROM items WHERE session_id = ? AND analysis = 'pending' ORDER BY seq",
                (session_id,),
            ).fetchall()
            previous_hashes = [
                row["perceptual_hash"]
                for row in connection.execute(
                    "SELECT perceptual_hash FROM items WHERE session_id = ? "
                    "AND analysis = 'done' AND perceptual_hash != '' ORDER BY seq",
                    (session_id,),
                )
            ]
        return [dict(row) for row in pending], previous_hashes

    @staticmethod
    def _hash_file(path):
        digest = hashlib.sha256()
        with open(path, "rb") as file:
            while chunk := file.read(HASH_CHUNK_BYTES):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _choose_copy_to_keep(copies):
        """Pick which of several identical files to keep.

        A copy that was already analyzed stays the kept one, so resuming a
        session never changes an earlier choice. Otherwise the shortest name
        wins, which keeps "IMG_1.jpg" over "IMG_1 - Copy.jpg" or
        "IMG_1 (1).jpg".
        """
        settled = [item for item in copies if item["analysis"] != "pending"]
        if settled:
            return settled[0]
        return min(copies, key=lambda item: (len(item["rel_path"]), item["rel_path"].lower()))

    def _discard_exact_copies(self, session_id):
        """Discard files that are byte-for-byte identical to another file.

        Identical files carry no extra information, so discarding the extras
        loses nothing. They go to the discarded folder like any other
        discard, so they can still be downloaded.
        """
        with self._write_lock:
            with self._connect() as connection:
                unhashed = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM items WHERE session_id = ? AND content_hash IS NULL",
                        (session_id,),
                    )
                ]
            for item in unhashed:
                try:
                    content_hash = self._hash_file(self.item_file_path(item))
                except OSError:
                    continue
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE items SET content_hash = ? WHERE id = ?", (content_hash, item["id"])
                    )

            with self._connect() as connection:
                items = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM items WHERE session_id = ? AND content_hash IS NOT NULL "
                        "ORDER BY seq",
                        (session_id,),
                    )
                ]
            copies_by_hash = {}
            for item in items:
                copies_by_hash.setdefault(item["content_hash"], []).append(item)

            for copies in copies_by_hash.values():
                if len(copies) < 2:
                    continue
                keeper = self._choose_copy_to_keep(copies)
                for item in copies:
                    if item["id"] == keeper["id"] or item["analysis"] != "pending":
                        continue
                    with self._connect() as connection:
                        connection.execute(
                            "UPDATE items SET analysis = 'skipped', reasons = ?, duplicate_of = ? "
                            "WHERE id = ?",
                            (json.dumps([EXACT_DUPLICATE]), keeper["id"], item["id"]),
                        )
                    self._apply_decision(self.get_item(item["id"]), DISCARD, "auto")

    def record_result(self, item_id, result):
        """Store one file's analysis and apply the automatic decisions.

        Kept automatically: videos (no review screen for them yet), files the
        analysis could not read, and photos the scorer classified as KEEP.
        Discarded automatically: photos the scorer classified as
        DISCARD_CANDIDATE. Everything else waits for the user.
        """
        with self._write_lock:
            item = self.get_item(item_id)
            if result is None:
                fields = {
                    "analysis": "failed",
                    "reasons": json.dumps([COULD_NOT_ANALYZE]),
                }
                auto_decision = KEEP
            else:
                fields = {
                    "analysis": "done",
                    "classification": result.classification,
                    "final_score": result.final_score,
                    "reasons": json.dumps(result.reasons),
                    "perceptual_hash": result.perceptual_hash,
                    "width": result.width,
                    "height": result.height,
                    "face_count": result.face_count,
                    "person_count": result.person_count,
                }
                if item["kind"] == "video" or result.classification == "KEEP":
                    auto_decision = KEEP
                elif result.classification == "DISCARD_CANDIDATE":
                    auto_decision = DISCARD
                else:
                    auto_decision = None

            assignments = ", ".join(f"{column} = ?" for column in fields)
            with self._connect() as connection:
                connection.execute(
                    f"UPDATE items SET {assignments} WHERE id = ?",
                    (*fields.values(), item_id),
                )
            if auto_decision:
                self._apply_decision(self.get_item(item_id), auto_decision, "auto")

    # ----- items and decisions -----------------------------------------------

    def get_item(self, item_id):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise NotFound("File not found")
        return dict(row)

    def _move_item(self, item, new_location):
        if item["location"] == new_location:
            return
        source = self.item_file_path(item)
        target = self.bucket_dir(item["session_id"], new_location) / item["rel_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)

    def _apply_decision(self, item, decision, decided_by):
        new_location = DECISION_TO_BUCKET[decision]
        self._move_item(item, new_location)
        try:
            with self._connect() as connection:
                connection.execute(
                    "UPDATE items SET decision = ?, decided_by = ?, decided_at = ?, location = ? "
                    "WHERE id = ?",
                    (decision, decided_by, _now(), new_location, item["id"]),
                )
                connection.execute(
                    "INSERT INTO decision_log (session_id, item_id, decision, decided_by, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (item["session_id"], item["id"], decision, decided_by, _now()),
                )
        except Exception:
            # Keep disk and database in agreement if the database write fails.
            self._move_item({**item, "location": new_location}, item["location"])
            raise

    def decide(self, item_id, decision):
        """Record the user's keep or discard choice for a photo under review."""
        if decision not in DECISION_TO_BUCKET:
            raise StorageError("Decision must be 'keep' or 'discard'")
        with self._write_lock:
            item = self.get_item(item_id)
            if item["kind"] != "image" or item["analysis"] != "done":
                raise StorageError("Only analyzed photos can be reviewed")
            if item["decided_by"] == "auto":
                raise StorageError("This file was kept automatically")
            if item["decision"] == decision:
                return self.get_item(item_id)
            self._apply_decision(item, decision, "user")
            return self.get_item(item_id)

    def undo_last(self, session_id):
        """Reverse the most recent user decision in a session.

        The file goes back to incoming/ and returns to the review queue.
        Returns the item, or None when there is nothing to undo.
        """
        with self._write_lock:
            with self._connect() as connection:
                entry = connection.execute(
                    "SELECT * FROM decision_log WHERE session_id = ? AND decided_by = 'user' "
                    "AND undone = 0 ORDER BY id DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
            if entry is None:
                return None
            item = self.get_item(entry["item_id"])
            self._move_item(item, INCOMING)
            with self._connect() as connection:
                connection.execute(
                    "UPDATE decision_log SET undone = 1 WHERE item_id = ? AND decided_by = 'user'",
                    (item["id"],),
                )
                connection.execute(
                    "UPDATE items SET decision = NULL, decided_by = NULL, decided_at = NULL, "
                    "location = ? WHERE id = ?",
                    (INCOMING, item["id"]),
                )
            return self.get_item(item["id"])

    # ----- state for the UI --------------------------------------------------

    @staticmethod
    def item_summary(item):
        return {
            "id": item["id"],
            "rel_path": item["rel_path"],
            "name": item["rel_path"].rsplit("/", 1)[-1],
            "kind": item["kind"],
            "classification": item["classification"],
            "final_score": item["final_score"],
            "reasons": json.loads(item["reasons"]) if item["reasons"] else [],
            "width": item["width"],
            "height": item["height"],
            "face_count": item["face_count"],
            "person_count": item["person_count"],
            "decision": item["decision"],
            "decided_by": item["decided_by"],
            "size_bytes": item["size_bytes"],
        }

    def session_state(self, session_id):
        session = self.get_session(session_id)
        with self._connect() as connection:
            items = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM items WHERE session_id = ? ORDER BY seq, rel_path",
                    (session_id,),
                )
            ]
            can_undo = (
                connection.execute(
                    "SELECT 1 FROM decision_log WHERE session_id = ? AND decided_by = 'user' "
                    "AND undone = 0 LIMIT 1",
                    (session_id,),
                ).fetchone()
                is not None
            )

        counts = {
            "total": len(items),
            "analyzed": sum(item["analysis"] != "pending" for item in items),
            "failed": sum(item["analysis"] == "failed" for item in items),
            "auto_kept": sum(
                item["decided_by"] == "auto" and item["decision"] == KEEP for item in items
            ),
            "auto_discarded": sum(
                item["decided_by"] == "auto" and item["decision"] == DISCARD for item in items
            ),
            "exact_duplicates": sum(item["analysis"] == "skipped" for item in items),
            "approved": sum(item["decision"] == KEEP for item in items),
            "discarded": sum(item["decision"] == DISCARD for item in items),
            "videos": sum(item["kind"] == "video" for item in items),
            "approved_bytes": sum(item["size_bytes"] for item in items if item["decision"] == KEEP),
            "discarded_bytes": sum(
                item["size_bytes"] for item in items if item["decision"] == DISCARD
            ),
        }
        queue = [
            self.item_summary(item)
            for item in items
            if item["kind"] == "image" and item["analysis"] == "done" and item["decision"] is None
        ]
        counts["waiting"] = len(queue)
        finished = session["status"] == "ready" and not queue
        return {
            "session": session,
            "counts": counts,
            "queue": queue,
            "can_undo": can_undo,
            "finished": finished,
            "folders": {bucket: str(self.bucket_dir(session_id, bucket)) for bucket in BUCKETS},
        }

    # ----- downloads ---------------------------------------------------------

    def build_zip(self, session_id, bucket):
        """Zip the approved or discarded folder into a temporary file.

        Photos and videos are already compressed, so files are stored without
        recompression, which keeps building the zip fast.
        """
        if bucket not in DOWNLOADABLE_BUCKETS:
            raise StorageError("Only the approved and discarded folders can be downloaded")
        self.get_session(session_id)
        folder = self.bucket_dir(session_id, bucket)
        exports = self.session_dir(session_id) / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        handle, zip_name = tempfile.mkstemp(dir=exports, suffix=".zip")
        os.close(handle)
        file_count = 0
        with self._write_lock:
            with zipfile.ZipFile(zip_name, "w", compression=zipfile.ZIP_STORED) as archive:
                for file in sorted(folder.rglob("*")):
                    if file.is_file() and not file.name.endswith(".part"):
                        archive.write(file, file.relative_to(folder).as_posix())
                        file_count += 1
        if file_count == 0:
            Path(zip_name).unlink(missing_ok=True)
            raise StorageError(f"The {bucket} folder is empty")
        return Path(zip_name)
