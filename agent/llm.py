"""LLM factory – the single place that decides which model/provider StudyPilot uses.

Both Groq (cloud) and Ollama (local, private) expose an OpenAI-compatible API,
so one ChatOpenAI class covers both; only base_url / model / key change.
"""
import os
from functools import lru_cache

import openai
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()  # reads .env from the project root (never printed anywhere)

GROQ_URL = "https://api.groq.com/openai/v1"
OLLAMA_URL = "http://localhost:11434/v1"

# Known-good Groq models (Groq retired the llama-3.x models used in the original plan).
DEFAULT_MODELS = {"main": "openai/gpt-oss-120b", "fast": "openai/gpt-oss-20b"}
ENV_KEYS = {"main": "MAIN_MODEL", "fast": "FAST_MODEL"}

# Errors that make us fall back from the big model to the small one.
FALLBACK_ERRORS = (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError)


class MissingKeyError(RuntimeError):
    """Raised when PROVIDER=groq but no GROQ_API_KEY is configured."""


def provider() -> str:
    return os.getenv("PROVIDER", "groq").strip().lower()


def _groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def has_api_key() -> bool:
    return provider() == "ollama" or bool(_groq_key())


@lru_cache(maxsize=1)
def available_models() -> frozenset:
    """Model ids this Groq key can use, fetched once per process (empty if the lookup fails)."""
    if provider() != "groq" or not _groq_key():
        return frozenset()
    try:
        client = openai.OpenAI(base_url=GROQ_URL, api_key=_groq_key(), timeout=10)
        return frozenset(m.id for m in client.models.list().data)
    except Exception:
        return frozenset()


def configured_model(kind: str = "main") -> str:
    return os.getenv(ENV_KEYS.get(kind, "MAIN_MODEL"), "").strip() or DEFAULT_MODELS[kind]


def model_name(kind: str = "main") -> str:
    """Model id for 'main' (final answers) or 'fast' (routing / grading).

    Self-healing: if the model in .env no longer exists on Groq, use a known-good default.
    """
    if provider() == "ollama":
        return os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    wanted = configured_model(kind)
    available = available_models()
    if available and wanted not in available and DEFAULT_MODELS[kind] in available:
        return DEFAULT_MODELS[kind]
    return wanted


def model_substitutions() -> list[dict]:
    """[{setting, configured, used}] for every .env model that had to be replaced."""
    if provider() != "groq":
        return []
    return [{"setting": ENV_KEYS[k], "configured": configured_model(k), "used": model_name(k)}
            for k in ("main", "fast") if configured_model(k) != model_name(k)]


def model_notice() -> str:
    """Human-readable note when a configured model had to be substituted (else '')."""
    return " ".join(f"{s['setting']} '{s['configured']}' is not available on Groq – using '{s['used']}'."
                    for s in model_substitutions())


def _chat(model: str, temperature: float, kind: str = "main") -> ChatOpenAI:
    """Build one ChatOpenAI client for the active provider."""
    if provider() == "ollama":
        return ChatOpenAI(base_url=OLLAMA_URL, api_key="ollama", model=model,
                          temperature=temperature, timeout=120)
    if not _groq_key():
        raise MissingKeyError("GROQ_API_KEY is missing – copy .env.example to .env and add your key.")
    extra = {}
    if kind == "fast" and model.startswith("openai/gpt-oss"):
        extra["reasoning_effort"] = "low"  # reasoning model: keep routing/grading quick
    return ChatOpenAI(base_url=GROQ_URL, api_key=_groq_key(), model=model,
                      temperature=temperature, timeout=60, max_retries=2, **extra)


def get_llm(kind: str = "main", temperature: float = 0.0, tools=None):
    """Return a chat model. kind='main' falls back to the FAST model if rate-limited.

    If `tools` is given, the tools are bound to both primary and fallback models
    (bind_tools must happen before with_fallbacks).
    """
    primary = _chat(model_name(kind), temperature, kind)
    if tools:
        primary = primary.bind_tools(tools)
    if kind == "main" and provider() == "groq":
        backup = _chat(model_name("fast"), temperature, "fast")
        if tools:
            backup = backup.bind_tools(tools)
        return primary.with_fallbacks([backup], exceptions_to_handle=FALLBACK_ERRORS)
    return primary


def friendly_error(err: Exception) -> str:
    """Turn API exceptions into a short message suitable for the UI."""
    if isinstance(err, MissingKeyError):
        return "🔑 No API key found. Copy `.env.example` to `.env` and add your GROQ_API_KEY."
    if isinstance(err, openai.AuthenticationError):
        return "🔑 The API key was rejected. Check GROQ_API_KEY in your `.env` file."
    if isinstance(err, openai.RateLimitError):
        return "⏳ The LLM provider is rate-limiting us. Wait ~30 seconds and try again."
    if isinstance(err, openai.APIConnectionError):
        if provider() == "ollama":
            return "🔌 Could not reach Ollama at localhost:11434. Is `ollama serve` running?"
        return "🌐 Could not reach the LLM provider. Check your internet connection."
    return f"⚠️ Something went wrong: {type(err).__name__}: {str(err)[:200]}"
