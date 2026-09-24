"""Walks the chosen folders, extracts + chunks + embeds new/changed files, and watches for changes."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import Config
from .db import DB, to_blob
from .embeddings import ClipEmbedder, TextEmbedder
from .extract import MAX_BYTES, SUPPORTED, extract, kind_of, months_mentioned

log = logging.getLogger(__name__)

SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", ".venv", "site-packages", "AppData", "Library", "$RECYCLE.BIN",
    "System Volume Information", "dist", "build", "target", ".git", "Program Files", "Windows",
}
MAX_CHUNKS_PER_FILE = 400
# Meaning-based search only needs the gist, so only the first chunks of a file are embedded (the slow part on
# laptop CPUs). Every chunk is still keyword-indexed, so exact words deep inside long PDFs remain findable.
EMBED_CHUNKS_PER_FILE = 24
OCR_WORKERS = max(2, (os.cpu_count() or 4) // 2)

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


@dataclass
class Progress:
    running: bool = False
    phase: str = "idle"  # idle | scanning | preparing | indexing | ocr | watching
    total: int = 0
    done: int = 0
    current: str = ""
    errors: int = 0
    last_finished: float | None = None
    recent_errors: list[str] = field(default_factory=list)
    fatal: str = ""  # set when a scan could not run at all (e.g. model download failed)


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "~")) and d not in SKIP_DIRS]
        for name in filenames:
            if name.startswith((".", "~$")):
                continue
            p = Path(dirpath) / name
            if p.suffix.lower() in SUPPORTED:
                yield p


def file_card(path: Path, kind: str, when: datetime) -> str:
    """A short synthetic chunk so the name, folder and date are searchable by meaning too."""
    label = {"image": "Image or photo", "pdf": "PDF document", "doc": "Word document",
             "sheet": "Spreadsheet", "slides": "Presentation", "text": "Text file"}.get(kind, "File")
    stem = path.stem.replace("_", " ").replace("-", " ")
    return f"{stem}. {label} in folder {path.parent.name}. From {when:%B %Y}."


class Indexer:
    def __init__(self, db: DB, cfg: Config, embedder: TextEmbedder, clip: ClipEmbedder) -> None:
        self.db = db
        self.cfg = cfg
        self.embedder = embedder
        self.clip = clip
        self.progress = Progress()
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._pending_lock = threading.Lock()
        self._observer = None
        self._stop = threading.Event()
        threading.Thread(target=self._drain_pending, daemon=True, name="watch-drain").start()

    # ---- full scans -------------------------------------------------------------------------

    def start_scan(self, force: bool = False) -> bool:
        if self.progress.running:
            return False
        threading.Thread(target=self._scan, args=(force,), daemon=True, name="scan").start()
        return True

    def _scan(self, force: bool) -> None:
        with self._lock:
            p = self.progress
            p.running, p.phase, p.done, p.total, p.errors, p.recent_errors = True, "scanning", 0, 0, 0, []
            p.fatal = ""
            try:
                roots = [Path(f) for f in self.cfg.settings.folders]
                known = {r["path"]: (r["mtime"], r["size"]) for r in self.db.query("SELECT path, mtime, size FROM files")}
                seen: set[str] = set()
                todo: list[Path] = []
                for root in roots:
                    for f in iter_files(root):
                        key = str(f)
                        seen.add(key)
                        try:
                            st = f.stat()
                        except OSError:
                            continue
                        if force or known.get(key) != (st.st_mtime, st.st_size):
                            todo.append(f)
                        p.current = key
                self._forget([path for path in known if path not in seen])

                # Newest first: the files people are hunting for are usually recent.
                todo.sort(key=lambda f: _safe_mtime(f), reverse=True)
                if todo and not self.embedder.ready:
                    # First run downloads the ~70 MB embedding model; say so instead of looking stuck.
                    p.phase, p.current = "preparing", ""
                    self.embedder.warm_up()
                # Pass 1: every file's text, name and date, skipping OCR, so search is useful within minutes.
                p.phase, p.total = "indexing", len(todo)
                for f in todo:
                    p.current = str(f)
                    self.index_file(f, ocr=False)
                    p.done += 1
                # Pass 2: read text from images and scanned PDFs, several at a time.
                self._ocr_pending()
            except Exception as e:
                log.exception("scan failed")
                p.recent_errors.append(f"Indexing stopped: {e}")
                p.fatal = str(e)
            finally:
                p.running, p.phase, p.current = False, "watching" if self._observer else "idle", ""
                p.last_finished = time.time()
        self.restart_watcher()

    def _forget(self, paths: list[str]) -> None:
        if not paths:
            return
        with self.db.tx() as c:
            for path in paths:
                row = c.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
                if row:
                    c.execute("DELETE FROM chunks WHERE file_id=?", (row["id"],))
                    c.execute("DELETE FROM image_vecs WHERE file_id=?", (row["id"],))
                    c.execute("DELETE FROM files WHERE id=?", (row["id"],))

    # ---- single file -------------------------------------------------------------------------

    def _ocr_pending(self) -> None:
        if not self.cfg.tesseract_cmd():
            return
        pending = [r["path"] for r in self.db.query("SELECT path FROM files WHERE ocr_pending=1 ORDER BY mtime DESC")]
        p = self.progress
        p.phase, p.total, p.done = "ocr", len(pending), 0
        counter = threading.Lock()

        def work(path: str) -> None:
            p.current = path
            try:
                self.index_file(Path(path), ocr=True)
            except Exception:
                log.exception("OCR pass failed for %s", path)
            with counter:
                p.done += 1

        with ThreadPoolExecutor(max_workers=OCR_WORKERS) as pool:
            list(pool.map(work, pending))

    def index_file(self, path: Path, ocr: bool = True) -> None:
        try:
            st = path.stat()
        except OSError:
            self._forget([str(path)])
            return
        kind = kind_of(path)
        mtime = datetime.fromtimestamp(st.st_mtime)
        ctime = _creation_time(st)
        status, error, ex = "ok", None, None
        if st.st_size > MAX_BYTES:
            status, error = "error", "File is larger than 60 MB; only its name is searchable."
        else:
            try:
                ex = extract(path, self.cfg.tesseract_cmd(), ocr=ocr)
            except Exception as e:  # corrupt files, permission errors, etc.
                status, error = "error", f"{type(e).__name__}: {e}"[:300]
                log.info("extract failed for %s: %s", path, error)
        if error:
            self.progress.errors += 1
            self.progress.recent_errors = (self.progress.recent_errors + [f"{path.name}: {error}"])[-20:]

        taken = ex.taken_at if ex else None
        when = taken or (min(mtime, datetime.fromtimestamp(ctime)) if ctime else mtime)
        docs: list[Document] = [Document(page_content=file_card(path, kind, when), metadata={"page": None, "card": True})]
        full_text = ""
        if ex and ex.pages:
            full_text = ex.text
            docs += splitter.split_documents(ex.pages)[:MAX_CHUNKS_PER_FILE]
        elif status == "ok" and not (ex and ex.needs_ocr):
            status = "empty"
        # docs[0] is the file card; embed it plus the first EMBED_CHUNKS_PER_FILE content chunks.
        n_embed = min(len(docs), EMBED_CHUNKS_PER_FILE + 1)
        vectors = list(self.embedder.embed_documents([d.page_content for d in docs[:n_embed]]))
        vectors += [None] * (len(docs) - n_embed)
        months = months_mentioned(full_text)
        if taken:
            months.insert(0, f"{taken:%Y-%m}")

        image_vec = None
        if kind == "image" and self.cfg.settings.photo_understanding:
            try:
                image_vec = self.clip.embed_images([str(path)])[0]
            except Exception as e:
                log.info("CLIP failed for %s: %s", path, e)

        with self.db.tx() as c:
            row = c.execute("SELECT id FROM files WHERE path=?", (str(path),)).fetchone()
            values = (path.name, str(path.parent), path.suffix.lower(), kind, st.st_size, st.st_mtime, ctime,
                      taken.timestamp() if taken else None, status, error, int(bool(ex and ex.ocr)),
                      " ".join(months), full_text[:600], time.time(), int(bool(ex and ex.needs_ocr)))
            if row:
                file_id = row["id"]
                c.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
                c.execute("DELETE FROM image_vecs WHERE file_id=?", (file_id,))
                c.execute("""UPDATE files SET name=?, folder=?, ext=?, kind=?, size=?, mtime=?, ctime=?, taken=?,
                             status=?, error=?, ocr=?, months=?, preview=?, indexed_at=?, ocr_pending=? WHERE id=?""",
                          (*values, file_id))
            else:
                file_id = c.execute("""INSERT INTO files (name, folder, ext, kind, size, mtime, ctime, taken, status,
                             error, ocr, months, preview, indexed_at, ocr_pending, path)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                    (*values, str(path))).lastrowid
            c.executemany(
                "INSERT INTO chunks (file_id, idx, page, text, embedding) VALUES (?,?,?,?,?)",
                [(file_id, -1 if d.metadata.get("card") else i, d.metadata.get("page"), d.page_content,
                  to_blob(v) if v is not None else b"")
                 for i, (d, v) in enumerate(zip(docs, vectors))],
            )
            if image_vec is not None:
                c.execute("INSERT INTO image_vecs (file_id, embedding) VALUES (?,?)", (file_id, to_blob(image_vec)))

    def move_record(self, old: str, new: str) -> None:
        """Keep a file's index entry (and id) when unlost itself renames it."""
        p = Path(new)
        with self.db.tx() as c:
            c.execute("UPDATE files SET path=?, name=?, folder=? WHERE path=?", (new, p.name, str(p.parent), old))

    # ---- watching ----------------------------------------------------------------------------

    def restart_watcher(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return
        if self._observer:
            self._observer.stop()
            self._observer = None
        roots = [f for f in self.cfg.settings.folders if Path(f).is_dir()]
        if not roots:
            return
        indexer = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                for attr in ("src_path", "dest_path"):
                    path = getattr(event, attr, None)
                    if path and Path(path).suffix.lower() in SUPPORTED and not Path(path).name.startswith((".", "~$")):
                        with indexer._pending_lock:
                            indexer._pending.add(str(path))

        obs = Observer()
        for r in roots:
            obs.schedule(Handler(), r, recursive=True)
        obs.daemon = True
        obs.start()
        self._observer = obs
        if not self.progress.running:
            self.progress.phase = "watching"

    def _drain_pending(self) -> None:
        # Debounce: downloads and saves fire many events; wait until a batch settles.
        while not self._stop.wait(3.0):
            if self.progress.running:
                continue
            with self._pending_lock:
                batch, self._pending = self._pending, set()
            roots = [Path(f) for f in self.cfg.settings.folders]
            for path in batch:
                p = Path(path)
                if not any(p.is_relative_to(r) for r in roots) or any(part in SKIP_DIRS for part in p.parts):
                    continue
                try:
                    if p.exists():
                        self.index_file(p)
                    else:
                        self._forget([path])
                except Exception:
                    log.exception("watch update failed for %s", path)

    def stop(self) -> None:
        self._stop.set()
        if self._observer:
            self._observer.stop()

    def snapshot(self) -> dict:
        return asdict(self.progress)


def _creation_time(st: os.stat_result) -> float:
    birth = getattr(st, "st_birthtime", None)
    if birth:
        return float(birth)
    return float(st.st_ctime) if os.name == "nt" else 0.0


def _safe_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0
