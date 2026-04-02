"""
Unified LLM client factory — routes to Anthropic, OpenAI, or Google based on model name.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import random
from typing import Any

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Maximum retries on transient errors (rate-limit, 529 overloaded, network glitches)
_MAX_RETRIES = 4
_BASE_BACKOFF = 2.0  # seconds — doubles each attempt, plus jitter

# Module-level singletons — reuse across all calls to avoid per-call httpx client creation
# which causes "cannot schedule new futures after shutdown" under concurrency
_anthropic_client = None
_openai_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
    return _anthropic_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai
        _openai_client = openai.AsyncOpenAI(api_key=settings.llm.openai_api_key)
    return _openai_client


class LLMProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    PERPLEXITY = "perplexity"


def _detect_provider(model: str) -> LLMProvider:
    model_lower = model.lower()
    if "claude" in model_lower:
        return LLMProvider.ANTHROPIC
    if any(tag in model_lower for tag in ("gpt", "o1", "o3", "codex", "dall")):
        return LLMProvider.OPENAI
    if "gemini" in model_lower:
        return LLMProvider.GOOGLE
    if "sonar" in model_lower or "pplx" in model_lower:
        return LLMProvider.PERPLEXITY
    return LLMProvider.OPENAI  # default fallback


async def complete(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Send a completion request to the appropriate provider."""

    model = model or settings.llm.primary_model
    provider = _detect_provider(model)

    if provider == LLMProvider.ANTHROPIC:
        return await _anthropic_complete(prompt, model, system, max_tokens, temperature)
    elif provider == LLMProvider.OPENAI:
        return await _openai_complete(prompt, model, system, max_tokens, temperature)
    elif provider == LLMProvider.GOOGLE:
        return await _google_complete(prompt, model, system, max_tokens, temperature)
    elif provider == LLMProvider.PERPLEXITY:
        return await _perplexity_complete(prompt, model, system, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown provider for model: {model}")


def _is_retryable(exc: Exception) -> bool:
    """Return True if this exception is a transient error worth retrying."""
    msg = str(exc).lower()
    retryable_signals = (
        "rate_limit", "rate limit", "429", "529", "overloaded",
        "timeout", "connection", "network", "service unavailable", "503",
        "internal server error", "500",
    )
    return any(s in msg for s in retryable_signals)


async def _with_retry(coro_fn, *args, **kwargs) -> str:
    """Call an async coroutine function with exponential backoff on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            if not _is_retryable(exc) or attempt == _MAX_RETRIES - 1:
                raise
            wait = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "LLM transient error (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, _MAX_RETRIES, exc, wait,
            )
            last_exc = exc
            await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


async def _anthropic_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    async def _call():
        client = _get_anthropic_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        response = await client.messages.create(**kwargs)
        return response.content[0].text

    return await _with_retry(_call)


async def _openai_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    client = _get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


async def _google_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.llm.google_api_key)
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system,
    )
    response = await gen_model.generate_content_async(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return response.text


async def _perplexity_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    import openai

    client = openai.AsyncOpenAI(
        api_key=settings.llm.perplexity_api_key,
        base_url="https://api.perplexity.ai",
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


async def complete_with_search(
    prompt: str,
    *,
    model: str = "claude-opus-4-6",
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    max_searches: int = 5,
) -> str:
    """Send a completion request to Claude with web search enabled."""
    async def _call():
        client = _get_anthropic_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_searches,
                }
            ],
        }
        if system:
            kwargs["system"] = system
        response = await client.messages.create(**kwargs)
        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_parts)

    return await _with_retry(_call)


def get_llm_client(provider: LLMProvider | None = None):
    """Return the raw provider client for advanced use. Defaults to Anthropic."""
    if provider is None or provider == LLMProvider.ANTHROPIC:
        return _get_anthropic_client()
    elif provider == LLMProvider.OPENAI:
        return _get_openai_client()
    raise ValueError(f"Raw client not supported for: {provider}")
