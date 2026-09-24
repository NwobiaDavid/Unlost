"""Speech-to-text for voice search: Groq's hosted Whisper (free tier) when a Groq key is set,
otherwise on-device faster-whisper if it's installed (pip install -r requirements-voice.txt)."""

from __future__ import annotations

import importlib.util
import io
import threading
from pathlib import Path

GROQ_WHISPER = "whisper-large-v3-turbo"

_model = None
_lock = threading.Lock()


def local_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def available(api_key: str | None) -> bool:
    return bool(api_key) or local_available()


def transcribe(audio: bytes, api_key: str | None, cache_dir: Path) -> str:
    if api_key:
        from groq import Groq

        result = Groq(api_key=api_key).audio.transcriptions.create(
            file=("speech.webm", audio), model=GROQ_WHISPER, language="en", response_format="json")
        return result.text.strip()
    return _transcribe_local(audio, cache_dir)


def _transcribe_local(audio: bytes, cache_dir: Path) -> str:
    global _model
    from faster_whisper import WhisperModel

    with _lock:
        if _model is None:
            # "base.en": ~140 MB, fast on CPU and good enough for short search phrases.
            _model = WhisperModel("base.en", device="cpu", compute_type="int8", download_root=str(cache_dir / "whisper"))
        segments, _ = _model.transcribe(io.BytesIO(audio), beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
