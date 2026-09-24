"""HTTP API the Electron app talks to. Bound to 127.0.0.1 and protected by a per-launch token."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import organize, qa, voice
from .config import MODEL_CHOICES, Config, data_dir
from .db import DB
from .embeddings import ClipEmbedder, TextEmbedder
from .indexer import Indexer
from .search import Searcher, file_dict

log = logging.getLogger(__name__)
TOKEN = os.environ.get("UNLOST_TOKEN") or secrets.token_urlsafe(24)


class State:
    def __init__(self) -> None:
        d = data_dir()
        self.cfg = Config()
        self.db = DB(d / "index.sqlite3")
        models = d / "models"
        self.embedder = TextEmbedder(models)
        self.clip = ClipEmbedder(models)
        self.indexer = Indexer(self.db, self.cfg, self.embedder, self.clip)
        self.searcher = Searcher(self.db, self.embedder, self.clip, lambda: self.cfg.settings.photo_understanding)
        self.thumbs = d / "thumbs"
        self.thumbs.mkdir(exist_ok=True)


S: State


@asynccontextmanager
async def lifespan(app: FastAPI):
    global S
    S = State()
    if S.cfg.settings.folders:
        S.indexer.start_scan()
    yield
    S.indexer.stop()


app = FastAPI(title="unlost sidecar", lifespan=lifespan)
# The renderer is served from file:// (origin "null") or the Vite dev server; the token is the real guard.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def auth(request: Request, token: str | None = Query(default=None)) -> None:
    supplied = request.headers.get("x-unlost-token") or token
    if not supplied or not secrets.compare_digest(supplied, TOKEN):
        raise HTTPException(401, "bad token")


@app.get("/health")
def health():
    return {"ok": True}


# ---- settings & status --------------------------------------------------------------------------

class SettingsIn(BaseModel):
    folders: list[str] | None = None
    model: str | None = None
    photo_understanding: bool | None = None
    tesseract_path: str | None = None
    onboarded: bool | None = None


@app.get("/settings", dependencies=[Depends(auth)])
def get_settings():
    return {**asdict(S.cfg.settings), "model_choices": MODEL_CHOICES}


@app.put("/settings", dependencies=[Depends(auth)])
def put_settings(body: SettingsIn):
    before = asdict(S.cfg.settings)
    after = asdict(S.cfg.update(**body.model_dump(exclude_none=True)))
    if before["folders"] != after["folders"] or (after["photo_understanding"] and not before["photo_understanding"]):
        S.indexer.start_scan(force=after["photo_understanding"] and not before["photo_understanding"])
    return {**after, "model_choices": MODEL_CHOICES}


class KeyIn(BaseModel):
    key: str | None


@app.post("/api-key", dependencies=[Depends(auth)])
def set_key(body: KeyIn):
    S.cfg.api_key = (body.key or "").strip() or None
    return {"has_api_key": bool(S.cfg.api_key)}


@app.get("/status", dependencies=[Depends(auth)])
def status():
    counts = S.db.one("""SELECT COUNT(*) AS files, SUM(status='error') AS errors, SUM(ocr) AS ocr,
                         SUM(kind='image') AS images FROM files""")
    return {
        "progress": S.indexer.snapshot(),
        "files": counts["files"] or 0,
        "errors": counts["errors"] or 0,
        "ocr_files": counts["ocr"] or 0,
        "images": counts["images"] or 0,
        "has_api_key": bool(S.cfg.api_key),
        "ocr_available": bool(S.cfg.tesseract_cmd()),
        "voice_available": voice.available(S.cfg.api_key),
        "voice_on_device": voice.local_available(),
        "last_organize": organize.last_batch(S.db),
    }


@app.post("/index/scan", dependencies=[Depends(auth)])
def scan(force: bool = False):
    return {"started": S.indexer.start_scan(force=force)}


# ---- search, files, thumbnails --------------------------------------------------------------------

@app.get("/search", dependencies=[Depends(auth)])
def search(q: str, limit: int = 30):
    q = q.strip()
    if not q:
        return {"results": []}
    return {"results": S.searcher.search(q, limit=min(limit, 100))}


@app.get("/files/{file_id}", dependencies=[Depends(auth)])
def file_detail(file_id: int):
    f = S.db.one("SELECT * FROM files WHERE id=?", (file_id,))
    if not f:
        raise HTTPException(404)
    text = "\n".join(r["text"] for r in S.db.query(
        "SELECT text FROM chunks WHERE file_id=? AND idx >= 0 ORDER BY idx LIMIT 6", (file_id,)))
    return {**file_dict(f), "text": text[:5000], "ocr": bool(f["ocr"]), "error": f["error"], "months": f["months"].split()}


@app.get("/thumb/{file_id}", dependencies=[Depends(auth)])
def thumb(file_id: int):
    f = S.db.one("SELECT path, kind, mtime FROM files WHERE id=?", (file_id,))
    if not f or f["kind"] not in ("image", "pdf"):
        raise HTTPException(404)
    out = S.thumbs / f"{file_id}_{int(f['mtime'])}.jpg"
    if not out.exists():
        try:
            _make_thumb(Path(f["path"]), f["kind"], out)
        except Exception:
            raise HTTPException(404)
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


def _make_thumb(src: Path, kind: str, out: Path) -> None:
    from PIL import Image, ImageOps

    if kind == "pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(src))
        try:
            im = pdf[0].render(scale=0.6).to_pil()
        finally:
            pdf.close()
    else:
        im = ImageOps.exif_transpose(Image.open(src))
    im = im.convert("RGB")
    im.thumbnail((320, 320))
    for old in out.parent.glob(out.name.split("_")[0] + "_*.jpg"):
        old.unlink(missing_ok=True)
    im.save(out, "JPEG", quality=82)


# ---- Q&A ----------------------------------------------------------------------------------------

class AskIn(BaseModel):
    question: str


@app.post("/ask", dependencies=[Depends(auth)])
async def ask(body: AskIn):
    async def events():
        async for ev in qa.answer(body.question.strip(), S.searcher, S.cfg):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---- organize -----------------------------------------------------------------------------------

class SuggestIn(BaseModel):
    folder: str
    include_all: bool = False


class ApplyIn(BaseModel):
    folder: str
    items: list[dict]


class UndoIn(BaseModel):
    batch_id: str


@app.post("/organize/suggest", dependencies=[Depends(auth)])
def organize_suggest(body: SuggestIn):
    try:
        return organize.suggest(S.db, S.cfg, body.folder, body.include_all)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/organize/apply", dependencies=[Depends(auth)])
def organize_apply(body: ApplyIn):
    try:
        return organize.apply(S.db, S.cfg, S.indexer, body.folder, body.items)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/organize/undo", dependencies=[Depends(auth)])
def organize_undo(body: UndoIn):
    return organize.undo(S.db, S.indexer, body.batch_id)


# ---- voice --------------------------------------------------------------------------------------

@app.post("/transcribe", dependencies=[Depends(auth)])
async def transcribe(request: Request):
    if not voice.available(S.cfg.api_key):
        raise HTTPException(501, "Voice search needs a Groq API key (or the optional faster-whisper package).")
    audio = await request.body()
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(413, "Recording too long")
    try:
        text = await asyncio.to_thread(voice.transcribe, audio, S.cfg.api_key, data_dir() / "models")
    except Exception as e:
        from .llm import friendly_error

        log.exception("transcription failed")
        raise HTTPException(502, friendly_error(e))
    return {"text": text}
