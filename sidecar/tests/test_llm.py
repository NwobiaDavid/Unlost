"""Groq wiring, exercised with fake models (no network, no key needed)."""

import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from unlost import llm, organize, qa
from unlost.config import MODEL_CHOICES


@pytest.mark.parametrize("model", MODEL_CHOICES)
def test_every_model_choice_builds(app_state, model):
    cfg, *_ = app_state
    cfg.api_key = "gsk_test"
    cfg.update(model=model)
    chat = llm.make_llm(cfg)
    assert chat.model_name == model
    assert (chat.reasoning_effort == "low") == (model in llm.REASONING_MODELS)
    llm.structured(cfg, organize.Suggestions)  # builds without error for both output methods


def test_ask_streams_answer_after_sources(app_state, monkeypatch):
    cfg, *_, searcher = app_state
    cfg.api_key = "gsk_test"
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="You paid N750,000 in total [1][2][3].")]))
    monkeypatch.setattr(qa, "make_llm", lambda cfg: fake)

    async def collect():
        return [e async for e in qa.answer("How much did I pay for rent in 2025?", searcher, cfg)]

    events = asyncio.run(collect())
    assert events[0]["type"] == "sources" and len(events[0]["sources"]) >= 3
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert text == "You paid N750,000 in total [1][2][3]."
    assert events[-1] == {"type": "done"}


def test_ask_reports_rate_limit_kindly(app_state, monkeypatch):
    import groq
    import httpx

    cfg, *_, searcher = app_state
    cfg.api_key = "gsk_test"
    resp = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com"))

    def boom(_):
        raise groq.RateLimitError("slow down", response=resp, body=None)

    monkeypatch.setattr(qa, "make_llm", lambda cfg: RunnableLambda(boom))

    async def collect():
        return [e async for e in qa.answer("rent", searcher, cfg)]

    err = next(e for e in asyncio.run(collect()) if e["type"] == "error")
    assert err["code"] == "rate_limit" and "free-tier limit" in err["message"]


def test_ai_organize_uses_model_suggestions(app_state, messy_folder, monkeypatch):
    cfg, db, *_ = app_state
    cfg.api_key = "gsk_test"
    fid = db.one("SELECT id FROM files WHERE name='document(3).pdf'")["id"]

    def fake_structured(cfg, schema):
        return RunnableLambda(lambda _: schema(items=[organize.Suggestion(
            file_id=fid, new_name="Canada Study Permit Guide", folder="Immigration", reason="IRCC guide")]))

    monkeypatch.setattr(llm, "structured", fake_structured)
    out = organize.suggest(db, cfg, str(messy_folder))
    assert out["used_ai"] is True
    item = next(i for i in out["items"] if i["file_id"] == fid)
    assert (item["new_name"], item["folder"]) == ("Canada Study Permit Guide.pdf", "Immigration")
