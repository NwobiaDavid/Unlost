import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("UNLOST_FAKE_EMBEDDINGS", "1")


def make_pdf(path: Path, lines: list[str]) -> None:
    """Write a minimal one-page PDF with a real text layer (no reportlab needed)."""
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for ln in lines:
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        text_ops.append(f"({esc}) Tj T*")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def make_text_image(path: Path, lines: list[str]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 120 + 80 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    for i, ln in enumerate(lines):
        draw.text((60, 60 + 80 * i), ln, fill="black", font=font)
    img.save(path)


def make_docx(path: Path, paragraphs: list[str]) -> None:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(path)


def set_mtime(path: Path, y: int, m: int, d: int = 15) -> None:
    t = time.mktime((y, m, d, 12, 0, 0, 0, 0, -1))
    os.utime(path, (t, t))


@pytest.fixture()
def messy_folder(tmp_path: Path) -> Path:
    root = tmp_path / "Downloads"
    root.mkdir()
    make_pdf(root / "document(3).pdf", [
        "Motor Insurance Policy - Comprehensive Cover",
        "Insured vehicle: Toyota Corolla 2018, registration LSR 482 KJ",
        "Policy period: 01 Feb 2026 to 31 Jan 2027. Annual premium: N185,000.",
    ])
    make_text_image(root / "IMG_4821.png", [
        "WEST AFRICAN EXAMINATIONS COUNCIL",
        "West African Senior School Certificate",
        "Candidate: Ada Obi   WAEC 2019",
    ])
    make_docx(root / "Untitled.docx", [
        "INVOICE #2031",
        "Billed to: Brightpath Design Ltd",
        "Website redesign, 40 hours at $60",
        "Total due: $2,400",
    ])
    set_mtime(root / "Untitled.docx", 2026, 3, 12)
    for month, name in [(1, "scan0001.txt"), (2, "scan0002.txt"), (3, "rent-march.txt")]:
        (root / name).write_text(f"Rent receipt. Received from Ada Obi the sum of N250,000 for rent, "
                                 f"month {month}/2025. Landlord: Mr Bello.", "utf-8")
        set_mtime(root / name, 2025, month, 2)
    (root / "notes.md").write_text("Grocery list: rice, beans, plantain, pepper.", "utf-8")
    return root


@pytest.fixture()
def app_state(tmp_path: Path, messy_folder: Path, monkeypatch):
    monkeypatch.setenv("UNLOST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from unlost.config import Config
    from unlost.db import DB
    from unlost.embeddings import ClipEmbedder, TextEmbedder
    from unlost.indexer import Indexer
    from unlost.search import Searcher

    cfg = Config()
    cfg.update(folders=[str(messy_folder)])
    db = DB(tmp_path / "data" / "index.sqlite3")
    emb = TextEmbedder(tmp_path / "models")
    clip = ClipEmbedder(tmp_path / "models")
    idx = Indexer(db, cfg, emb, clip)
    idx._scan(force=False)
    yield cfg, db, idx, Searcher(db, emb, clip, lambda: False)
    idx.stop()
