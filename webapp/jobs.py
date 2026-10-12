"""Runs folder analysis in the background, one thread per session."""

import threading
import traceback

from file_scanner import apply_duplicate_check, iter_analyzed


class AnalysisRunner:
    def __init__(self, store, workers=None):
        self.store = store
        self.workers = workers
        self._lock = threading.Lock()
        self._threads = {}
        self._stop_events = {}

    def is_running(self, session_id):
        with self._lock:
            thread = self._threads.get(session_id)
            return thread is not None and thread.is_alive()

    def start(self, session_id):
        """Start or resume analysis. Does nothing if it is already running."""
        with self._lock:
            thread = self._threads.get(session_id)
            if thread is not None and thread.is_alive():
                return False
            pending, previous_hashes = self.store.begin_analysis(session_id)
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._run,
                args=(session_id, pending, previous_hashes, stop_event),
                name=f"analysis-{session_id}",
                daemon=True,
            )
            self._threads[session_id] = thread
            self._stop_events[session_id] = stop_event
            thread.start()
            return True

    def stop(self, session_id, timeout=60):
        with self._lock:
            thread = self._threads.get(session_id)
            stop_event = self._stop_events.get(session_id)
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout)

    def stop_all(self, timeout=30):
        """Stop every running analysis, used when the server shuts down.

        Each session is left marked as analyzing, and the next server start
        marks it interrupted so the app offers to resume it.
        """
        with self._lock:
            sessions = list(self._threads)
        for event in [self._stop_events[session_id] for session_id in sessions]:
            event.set()
        for session_id in sessions:
            self._threads[session_id].join(timeout)

    def _run(self, session_id, pending, previous_hashes, stop_event):
        media = [
            (self.store.bucket_dir(session_id, item["location"]) / item["rel_path"], item["kind"])
            for item in pending
        ]
        results = iter_analyzed(media, self.workers)
        try:
            for item, (_, result) in zip(pending, results):
                if stop_event.is_set():
                    break
                if result is not None and item["kind"] == "image":
                    # Same rule as the command-line scan: compare each photo
                    # with every photo before it.
                    result = apply_duplicate_check(result, previous_hashes)
                    previous_hashes.append(result.perceptual_hash)
                self.store.record_result(item["id"], result)
        except Exception as error:
            traceback.print_exc()
            self._set_status_if_present(session_id, "interrupted", f"Analysis stopped: {error}")
            return
        finally:
            results.close()

        if not stop_event.is_set():
            self._set_status_if_present(session_id, "ready")

    def _set_status_if_present(self, session_id, status, error=None):
        try:
            self.store.set_status(session_id, status, error)
        except Exception:
            # The session may have been deleted while analysis was stopping.
            pass
