"""Local embeddings (nothing leaves the machine) and an in-memory cosine index over them."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from pathlib import Path

import numpy as np

from .db import DB, from_blob

TEXT_MODEL = "BAAI/bge-small-en-v1.5"  # 384-d, ~70 MB, fast on CPU
CLIP_VISION = "Qdrant/clip-ViT-B-32-vision"
CLIP_TEXT = "Qdrant/clip-ViT-B-32-text"
RELOAD_INTERVAL = 3.0  # seconds


def _normalize(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.maximum(norms, 1e-9)


class TextEmbedder:
    """fastembed (ONNX, CPU) text embeddings. Set UNLOST_FAKE_EMBEDDINGS=1 in tests to skip the model."""

    dim = 384

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()
        self.fake = os.environ.get("UNLOST_FAKE_EMBEDDINGS") == "1"

    @property
    def model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(TEXT_MODEL, cache_dir=str(self._cache_dir))
        return self._model

    @property
    def ready(self) -> bool:
        return self.fake or self._model is not None

    def warm_up(self) -> None:
        with self._lock:
            _ = self.model

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        if self.fake:
            return np.stack([_fake_vec(t, self.dim) for t in texts])
        with self._lock:
            return _normalize(list(self.model.embed(texts, batch_size=32)))

    def embed_query(self, text: str) -> np.ndarray:
        if self.fake:
            return _fake_vec(text, self.dim)
        with self._lock:
            return _normalize(next(iter(self.model.query_embed(text))))


class ClipEmbedder:
    """CLIP puts photos and text in the same space, so "beach sunset" can find IMG_4821.jpg with no OCR text."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = str(cache_dir)
        self._vision = None
        self._text = None
        self._lock = threading.Lock()

    def embed_images(self, paths: list[str]) -> np.ndarray:
        from fastembed import ImageEmbedding

        with self._lock:
            if self._vision is None:
                self._vision = ImageEmbedding(CLIP_VISION, cache_dir=self._cache_dir)
            return _normalize(list(self._vision.embed(paths)))

    def embed_query(self, text: str) -> np.ndarray:
        from fastembed import TextEmbedding

        with self._lock:
            if self._text is None:
                self._text = TextEmbedding(CLIP_TEXT, cache_dir=self._cache_dir)
            return _normalize(next(iter(self._text.embed([text]))))


class VectorIndex:
    """Brute-force cosine search. A personal index is at most ~10^5 chunks, which numpy scans in milliseconds."""

    def __init__(self, db: DB, table: str) -> None:
        assert table in ("chunks", "image_vecs")
        self.db = db
        self.table = table
        self._generation = -1
        self._ids = np.zeros(0, dtype=np.int64)
        self._file_ids = np.zeros(0, dtype=np.int64)
        self._matrix: np.ndarray | None = None
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        if self._generation == self.db.generation:
            return
        # While indexing, the DB changes every few ms; reloading on every keystroke would make search sluggish.
        if self._matrix is not None and time.monotonic() - self._loaded_at < RELOAD_INTERVAL:
            return
        gen = self.db.generation
        if self.table == "chunks":
            rows = self.db.query("SELECT id, file_id, embedding FROM chunks WHERE length(embedding) > 0")
        else:
            rows = self.db.query("SELECT file_id AS id, file_id, embedding FROM image_vecs")
        self._ids = np.array([r["id"] for r in rows], dtype=np.int64)
        self._file_ids = np.array([r["file_id"] for r in rows], dtype=np.int64)
        self._matrix = np.stack([from_blob(r["embedding"]) for r in rows]) if rows else None
        self._generation = gen
        self._loaded_at = time.monotonic()

    def search(self, query_vec: np.ndarray, k: int = 200) -> list[tuple[int, int, float]]:
        """Returns (row id, file id, cosine similarity), best first."""
        with self._lock:
            self._refresh()
            if self._matrix is None:
                return []
            sims = self._matrix @ query_vec.astype(np.float32)
            k = min(k, len(sims))
            top = np.argpartition(-sims, k - 1)[:k]
            top = top[np.argsort(-sims[top])]
            return [(int(self._ids[i]), int(self._file_ids[i]), float(sims[i])) for i in top]


def _fake_vec(text: str, dim: int) -> np.ndarray:
    """Deterministic bag-of-words hashing embedding, so tests don't need to download a model."""
    v = np.zeros(dim, dtype=np.float32)
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v
