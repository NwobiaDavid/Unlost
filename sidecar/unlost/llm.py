"""The language model behind Ask and Organize: Groq (free tier) via LangChain's ChatGroq."""

from __future__ import annotations

from .config import Config

# Groq production models. gpt-oss models reason before answering and support strict JSON-schema output.
REASONING_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}


def make_llm(cfg: Config, streaming: bool = True):
    from langchain_groq import ChatGroq

    kwargs = {}
    if cfg.settings.model in REASONING_MODELS:
        # Low effort keeps answers fast and within the free tier's tokens-per-minute budget;
        # "hidden" keeps the model's reasoning out of the streamed answer.
        kwargs.update(reasoning_effort="low", reasoning_format="hidden")
    return ChatGroq(
        model=cfg.settings.model,
        api_key=cfg.api_key,
        max_tokens=4096,
        temperature=0.2,
        streaming=streaming,
        max_retries=3,  # the SDK waits out 429s using Groq's retry-after header
        **kwargs,
    )


def structured(cfg: Config, schema):
    """An LLM that returns `schema` instances: strict JSON schema where supported, tool calling otherwise."""
    method = "json_schema" if cfg.settings.model in REASONING_MODELS else "function_calling"
    return make_llm(cfg, streaming=False).with_structured_output(schema, method=method)


def error_code(e: Exception) -> str:
    import groq

    if isinstance(e, groq.AuthenticationError):
        return "auth"
    if isinstance(e, groq.RateLimitError):
        return "rate_limit"
    if isinstance(e, groq.APIConnectionError):
        return "offline"
    return "api"


def friendly_error(e: Exception) -> str:
    return {
        "auth": "Your Groq API key was rejected. Check it in Settings.",
        "rate_limit": "You've hit Groq's free-tier limit for now. Wait a minute and try again, "
                      "or pick a smaller model in Settings.",
        "offline": "Couldn't reach Groq. Check your internet connection. Search still works offline.",
    }.get(error_code(e), f"Groq returned an error: {e}")
