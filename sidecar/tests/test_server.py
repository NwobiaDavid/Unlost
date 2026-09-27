import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, messy_folder, monkeypatch):
    monkeypatch.setenv("UNLOST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UNLOST_TOKEN", "t0k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    import importlib

    import unlost.server as server

    importlib.reload(server)
    with TestClient(server.app) as c:
        c.headers["x-unlost-token"] = "t0k"
        yield c, server


def test_requires_token(client):
    c, _ = client
    assert c.get("/status", headers={"x-unlost-token": "nope"}).status_code == 401
    assert c.get("/health").status_code == 200


def test_settings_search_and_ask_without_key(client, messy_folder):
    c, server = client
    r = c.put("/settings", json={"folders": [str(messy_folder)], "onboarded": True})
    assert r.status_code == 200 and r.json()["folders"] == [str(messy_folder)]
    import time

    for _ in range(300):
        st = c.get("/status").json()
        if not st["progress"]["running"] and st["files"] == 7:
            break
        time.sleep(0.1)
    assert st["files"] == 7 and st["has_api_key"] is False

    res = c.get("/search", params={"q": "car insurance policy"}).json()["results"]
    assert res[0]["name"] == "document(3).pdf"
    assert c.get(f"/thumb/{res[0]['id']}").headers["content-type"] == "image/jpeg"
    assert c.get(f"/files/{res[0]['id']}").json()["kind"] == "pdf"

    with c.stream("POST", "/ask", json={"question": "how much was the rent"}) as s:
        events = [json.loads(line[6:]) for line in s.iter_lines() if line.startswith("data: ")]
    assert events[0]["type"] == "sources" and events[0]["sources"]
    assert any(e["type"] == "error" and e["code"] == "no_api_key" for e in events)
    assert events[-1]["type"] == "done"


def test_organize_rejects_unindexed_folder(client, tmp_path):
    c, _ = client
    assert c.post("/organize/suggest", json={"folder": str(tmp_path)}).status_code == 400
