from pathlib import Path

import pytest

from unlost import organize


@pytest.mark.parametrize("name,messy", [
    ("IMG_4821.jpg", True), ("document(3).pdf", True), ("Screenshot 2025-03-02 101112.png", True),
    ("Untitled.docx", True), ("WhatsApp Image 2024-01-01 at 10.00.00.jpeg", True), ("scan0001.pdf", True),
    ("a3f9c2e1b7d04e2a.pdf", True), ("Report - copy.docx", True),
    ("Rent Receipt - March 2025.pdf", False), ("CV Ada Obi.docx", False), ("notes.md", False),
])
def test_is_messy(name, messy):
    assert organize.is_messy(name) is messy


def test_clean_name_blocks_path_tricks():
    assert organize.clean_name('../../evil:name?') == "evil name"
    assert organize.clean_folder("..") == ""
    assert organize.clean_folder("Finance/2025") == "Finance 2025"
    assert organize.clean_name("CON") == ""


def test_local_suggestions_apply_and_undo(app_state, messy_folder: Path):
    cfg, db, idx, _ = app_state
    out = organize.suggest(db, cfg, str(messy_folder))
    assert out["used_ai"] is False
    by_name = {i["name"]: i for i in out["items"]}
    assert "notes.md" not in by_name and "rent-march.txt" not in by_name
    assert by_name["Untitled.docx"]["folder"] == "Finance"
    assert by_name["IMG_4821.png"]["folder"] == "Education"
    assert by_name["document(3).pdf"]["folder"] == "Finance"

    item = by_name["document(3).pdf"]
    res = organize.apply(db, cfg, idx, str(messy_folder), [{**item, "new_name": "Car Insurance Policy 2026.pdf"}])
    dest = messy_folder / "Finance" / "Car Insurance Policy 2026.pdf"
    assert res["skipped"] == [] and dest.exists() and not (messy_folder / "document(3).pdf").exists()
    row = db.one("SELECT path FROM files WHERE id=?", (item["file_id"],))
    assert row["path"] == str(dest)  # same index entry, new location

    assert organize.undo(db, idx, res["batch_id"])["restored"] == 1
    assert (messy_folder / "document(3).pdf").exists()
    assert not (messy_folder / "Finance").exists()


def test_apply_never_overwrites_and_rejects_outside_root(app_state, messy_folder: Path, tmp_path: Path):
    cfg, db, idx, _ = app_state
    (messy_folder / "Notes").mkdir()
    (messy_folder / "Notes" / "Rent.txt").write_text("existing", "utf-8")
    fid = db.one("SELECT id FROM files WHERE name='scan0001.txt'")["id"]
    res = organize.apply(db, cfg, idx, str(messy_folder), [{"file_id": fid, "new_name": "Rent", "folder": "Notes"}])
    assert Path(res["moved"][0]["to"]).name == "Rent (2).txt"
    assert (messy_folder / "Notes" / "Rent.txt").read_text("utf-8") == "existing"

    with pytest.raises(ValueError):
        organize.suggest(db, cfg, str(tmp_path))


def test_local_title_uses_content_month_and_sane_caps():
    s = organize._local_suggest({"id": 1, "name": "IMG_1.png", "kind": "image", "mtime": 1790000000, "taken": None,
                                 "months": "2019-06", "preview": "WEST AFRICAN EXAMINATIONS COUNCIL\nresult"})
    assert s.new_name == "West African Examinations Council - Jun 2019"
