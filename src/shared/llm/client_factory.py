"""
Unified LLM client factory — routes to Anthropic, OpenAI, or Google based on model name.
"""

from __future__ import annotations

import enum
import logging
from typing import Any

from src.config.settings import settings

logger = logging.getLogger(__name__)


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


async def _anthropic_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
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


async def _openai_complete(
    prompt: str, model: str, system: str | None, max_tokens: int, temperature: float
) -> str:
    import openai

    client = openai.AsyncOpenAI(api_key=settings.llm.openai_api_key)
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
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
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

    # Extract text blocks from the response (skip tool_use / search result blocks)
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    return "\n".join(text_parts)


def get_llm_client(provider: LLMProvider | None = None):
    """Return the raw provider client for advanced use."""
    if provider == LLMProvider.ANTHROPIC:
        import anthropic
        return anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
    elif provider == LLMProvider.OPENAI:
        import openai
        return openai.AsyncOpenAI(api_key=settings.llm.openai_api_key)
    raise ValueError(f"Raw client not supported for: {provider}")
