"""PhotoThin review web app.

Start it with:  python -m webapp
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from file_scanner import SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS, media_kind
from webapp.jobs import AnalysisRunner
from webapp.previews import ensure_preview
from webapp.storage import NotFound, Store, StorageError

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "webapp_data"


class CreateSessionRequest(BaseModel):
    name: str = ""


class DecisionRequest(BaseModel):
    decision: str


def _workers_from_env():
    value = os.environ.get("PHOTOTHIN_WORKERS")
    return int(value) if value else None


def create_app(data_dir=None, workers=None):
    data_dir = Path(data_dir or os.environ.get("PHOTOTHIN_DATA_DIR") or DEFAULT_DATA_DIR)
    store = Store(data_dir)
    runner = AnalysisRunner(store, workers if workers is not None else _workers_from_env())

    @asynccontextmanager
    async def lifespan(_app):
        yield
        runner.stop_all()

    app = FastAPI(title="PhotoThin", lifespan=lifespan)
    app.state.store = store
    app.state.runner = runner
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def session_or_404(session_id):
        try:
            return store.get_session(session_id)
        except NotFound as error:
            raise HTTPException(status_code=404, detail=str(error))

    def item_or_404(item_id):
        try:
            return store.get_item(item_id)
        except NotFound as error:
            raise HTTPException(status_code=404, detail=str(error))

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/config")
    def config():
        return {
            "image_extensions": sorted(SUPPORTED_IMAGE_EXTENSIONS),
            "video_extensions": sorted(SUPPORTED_VIDEO_EXTENSIONS),
        }

    @app.get("/api/sessions")
    def list_sessions():
        sessions = store.list_sessions()
        for session in sessions:
            session["running"] = runner.is_running(session["id"])
        return sessions

    @app.post("/api/sessions", status_code=201)
    def create_session(request: CreateSessionRequest):
        session_id = store.create_session(request.name)
        return store.get_session(session_id)

    @app.get("/api/sessions/{session_id}")
    def session_state(session_id: str):
        session_or_404(session_id)
        state = store.session_state(session_id)
        state["running"] = runner.is_running(session_id)
        return state

    @app.delete("/api/sessions/{session_id}", status_code=204)
    def delete_session(session_id: str):
        session_or_404(session_id)
        runner.stop(session_id)
        store.delete_session(session_id)

    @app.post("/api/sessions/{session_id}/files", status_code=201)
    def upload_file(session_id: str, rel_path: str = Form(...), file: UploadFile = File(...)):
        session_or_404(session_id)
        kind = media_kind(rel_path)
        if kind is None:
            raise HTTPException(status_code=415, detail="Not a supported photo or video type")
        try:
            return store.add_upload(session_id, rel_path, kind, file.file)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except StorageError as error:
            raise HTTPException(status_code=409, detail=str(error))

    @app.post("/api/sessions/{session_id}/analyze", status_code=202)
    def start_analysis(session_id: str):
        session_or_404(session_id)
        started = runner.start(session_id)
        return {"started": started}

    @app.post("/api/sessions/{session_id}/undo")
    def undo(session_id: str):
        session_or_404(session_id)
        item = store.undo_last(session_id)
        if item is None:
            raise HTTPException(status_code=409, detail="Nothing to undo")
        return store.item_summary(item)

    @app.post("/api/items/{item_id}/decision")
    def decide(item_id: int, request: DecisionRequest):
        item_or_404(item_id)
        try:
            item = store.decide(item_id, request.decision)
        except StorageError as error:
            raise HTTPException(status_code=409, detail=str(error))
        return store.item_summary(item)

    @app.get("/api/items/{item_id}/preview")
    def preview(item_id: int):
        item = item_or_404(item_id)
        if item["kind"] != "image":
            raise HTTPException(status_code=404, detail="Previews are only made for photos")
        try:
            path = ensure_preview(store.item_file_path(item), store.preview_path(item))
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=f"Could not make a preview: {error}")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/sessions/{session_id}/download/{bucket}")
    def download(session_id: str, bucket: str):
        session = session_or_404(session_id)
        try:
            zip_path = store.build_zip(session_id, bucket)
        except StorageError as error:
            raise HTTPException(status_code=409, detail=str(error))
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in session["name"]).strip()
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{safe_name or 'photothin'} - {bucket}.zip",
            background=BackgroundTask(zip_path.unlink, missing_ok=True),
        )

    return app
