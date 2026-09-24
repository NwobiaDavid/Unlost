"""SQLite storage: file metadata, text chunks (+FTS5), embeddings, organize history."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import numpy as np

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    folder      TEXT NOT NULL,
    ext         TEXT NOT NULL,
    kind        TEXT NOT NULL,
    size        INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    ctime       REAL NOT NULL DEFAULT 0,  -- creation time where the OS reports it (download date)
    taken       REAL,                     -- EXIF capture time for photos
    status      TEXT NOT NULL,          -- ok | error | empty
    error       TEXT,
    ocr         INTEGER NOT NULL DEFAULT 0,
    months      TEXT NOT NULL DEFAULT '',  -- space-separated YYYY-MM mentioned in the content
    preview     TEXT NOT NULL DEFAULT '',
    indexed_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS files_folder ON files(folder);

CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY,
    file_id   INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    idx       INTEGER NOT NULL,
    page      INTEGER,
    text      TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_file ON chunks(file_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id', tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS names_fts USING fts5(
    name, content='files', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO names_fts(rowid, name) VALUES (new.id, new.name);
END;
CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO names_fts(names_fts, rowid, name) VALUES ('delete', old.id, old.name);
END;
CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE OF name ON files BEGIN
    INSERT INTO names_fts(names_fts, rowid, name) VALUES ('delete', old.id, old.name);
    INSERT INTO names_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TABLE IF NOT EXISTS image_vecs (
    file_id   INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS organize_log (
    id        INTEGER PRIMARY KEY,
    batch_id  TEXT NOT NULL,
    old_path  TEXT NOT NULL,
    new_path  TEXT NOT NULL,
    ts        REAL NOT NULL,
    undone    INTEGER NOT NULL DEFAULT 0
);
"""


class DB:
    """One shared connection guarded by a lock; the sidecar's load is tiny, so this keeps things simple."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.executescript(SCHEMA)
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(files)")}
        if "ocr_pending" not in cols:  # added after the first release
            self._conn.execute("ALTER TABLE files ADD COLUMN ocr_pending INTEGER NOT NULL DEFAULT 0")
        # Bumped on every write that changes embeddings, so in-memory vector matrices know to reload.
        self.generation = 0

    @contextmanager
    def tx(self):
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
                self.generation += 1
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()


def to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
