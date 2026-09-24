"""Settings and paths. Settings live in <data_dir>/settings.json; the API key is memory-only."""

from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_MODEL = "openai/gpt-oss-120b"
MODEL_CHOICES = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def data_dir() -> Path:
    d = Path(os.environ.get("UNLOST_DATA_DIR") or Path.home() / ".unlost")
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    folders: list[str] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    # CLIP image embeddings: finds photos with no text in them ("sunset at the beach").
    # Off by default because the model is a ~600 MB download.
    photo_understanding: bool = False
    tesseract_path: str = ""
    onboarded: bool = False


class Config:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path = data_dir() / "settings.json"
        self.settings = self._load()
        self.api_key: str | None = os.environ.get("GROQ_API_KEY") or None

    def _load(self) -> Settings:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text("utf-8"))
                known = {k: v for k, v in raw.items() if k in Settings.__dataclass_fields__}
                s = Settings(**known)
                if s.model not in MODEL_CHOICES:  # e.g. a model from an older version of unlost
                    s.model = DEFAULT_MODEL
                return s
            except (json.JSONDecodeError, TypeError):
                pass
        return Settings()

    def update(self, **changes) -> Settings:
        with self._lock:
            for k, v in changes.items():
                if k in Settings.__dataclass_fields__ and v is not None:
                    setattr(self.settings, k, v)
            if self.settings.model not in MODEL_CHOICES:
                self.settings.model = DEFAULT_MODEL
            self.settings.folders = _dedupe_folders(self.settings.folders)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self.settings), indent=2), "utf-8")
            tmp.replace(self._path)
            return self.settings

    def tesseract_cmd(self) -> str | None:
        if self.settings.tesseract_path and Path(self.settings.tesseract_path).exists():
            return self.settings.tesseract_path
        found = shutil.which("tesseract")
        if found:
            return found
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Tesseract-OCR/tesseract.exe",
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
            Path("/opt/homebrew/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
        ]
        return next((str(c) for c in candidates if c.exists()), None)


def _dedupe_folders(folders: list[str]) -> list[str]:
    """Normalise, drop missing paths, and drop folders nested inside another selected folder."""
    paths = sorted({str(Path(f).expanduser().resolve()) for f in folders if f and Path(f).expanduser().is_dir()})
    result: list[str] = []
    for p in paths:
        if not any(Path(p).is_relative_to(r) for r in result):
            result.append(p)
    return result
