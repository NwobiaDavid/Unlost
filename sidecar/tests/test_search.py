from datetime import date

import pytest

from unlost.config import Config


def names(results):
    return [r["name"] for r in results]


def test_everything_indexed(app_state):
    _, db, idx, _ = app_state
    rows = {r["name"]: r for r in db.query("SELECT * FROM files")}
    assert set(rows) == {"document(3).pdf", "IMG_4821.png", "Untitled.docx", "scan0001.txt", "scan0002.txt",
                         "rent-march.txt", "notes.md"}
    assert idx.progress.errors == 0


@pytest.mark.skipif(not Config().tesseract_cmd(), reason="Tesseract not installed")
def test_photo_found_by_text_in_it(app_state):
    *_, searcher = app_state
    res = searcher.search("the photo of my WAEC certificate")
    assert names(res)[0] == "IMG_4821.png"
    assert "Text read from image" in res[0]["reasons"]


def test_pdf_found_by_topic_not_name(app_state):
    *_, searcher = app_state
    res = searcher.search("the PDF about Canadian study permits")
    assert names(res)[0] == "document(3).pdf"
    assert "permit" in res[0]["snippet"].lower()


def test_date_and_content_find_invoice(app_state):
    *_, searcher = app_state
    res = searcher.search("that invoice I sent in March", today=date(2026, 9, 24))
    assert names(res)[0] == "Untitled.docx"
    assert "March 2026" in res[0]["reasons"]


def test_filename_search_still_works(app_state):
    *_, searcher = app_state
    assert names(searcher.search("notes"))[0] == "notes.md"


def test_nonsense_query_returns_little(app_state):
    *_, searcher = app_state
    assert searcher.search("zebra quantum saxophone") == []


def test_rent_question_retrieves_all_receipts(app_state):
    *_, searcher = app_state
    chunks = searcher.retrieve_chunks("How much did I pay for rent last year?", today=date(2026, 9, 24))
    got = {c["name"] for c in chunks[:5]}
    assert {"scan0001.txt", "scan0002.txt", "rent-march.txt"} <= got


def test_reindex_is_incremental_and_tracks_deletes(app_state, messy_folder):
    _, db, idx, _ = app_state
    before = db.one("SELECT indexed_at FROM files WHERE name='notes.md'")["indexed_at"]
    (messy_folder / "scan0001.txt").unlink()
    idx._scan(force=False)
    assert idx.progress.total == 0  # nothing changed needed re-extraction
    assert db.one("SELECT indexed_at FROM files WHERE name='notes.md'")["indexed_at"] == before
    assert db.one("SELECT 1 FROM files WHERE name='scan0001.txt'") is None
    assert db.one("SELECT COUNT(*) AS n FROM chunks_fts WHERE chunks_fts MATCH 'scan0001'")["n"] == 0


def test_type_words_do_not_match_every_file_card(app_state):
    *_, searcher = app_state
    from unlost.search import keywords

    assert keywords("the photo of my WAEC certificate") == ["waec", "certificate"]


def test_answer_sources_exclude_file_cards(app_state):
    *_, searcher = app_state
    chunks = searcher.retrieve_chunks("rent receipt", today=date(2026, 9, 24))
    assert chunks and all("Text file in folder" not in c["text"] for c in chunks)


def test_two_pass_indexing_defers_then_finishes_ocr(app_state, messy_folder):
    from unlost.config import Config

    _, db, idx, _ = app_state
    img = messy_folder / "IMG_9999.png"
    img.write_bytes((messy_folder / "IMG_4821.png").read_bytes())
    idx.index_file(img, ocr=False)  # what pass 1 does
    row = db.one("SELECT ocr_pending, status, preview FROM files WHERE name='IMG_9999.png'")
    assert row["ocr_pending"] == 1 and row["status"] == "ok" and row["preview"] == ""
    if Config().tesseract_cmd():
        idx._ocr_pending()  # pass 2
        row = db.one("SELECT ocr_pending, preview FROM files WHERE name='IMG_9999.png'")
        assert row["ocr_pending"] == 0 and "EXAMINATIONS" in row["preview"]
