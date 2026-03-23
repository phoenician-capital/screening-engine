"""
Embedding service — wraps OpenAI or other embedding providers.
"""

from __future__ import annotations

import logging

import openai

from src.config.settings import settings

logger = logging.getLogger(__name__)

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(api_key=settings.llm.openai_api_key)
    return _client


async def embed_texts(
    texts: list[str],
    model: str | None = None,
) -> list[list[float]]:
    """Embed a batch of texts. Returns list of embedding vectors."""

    model = model or settings.llm.embedding_model
    client = _get_client()

    # OpenAI API supports batching up to ~8K tokens per request
    response = await client.embeddings.create(
        model=model,
        input=texts,
    )

    embeddings = [item.embedding for item in response.data]
    logger.info(
        "Embedded %d texts (%d tokens used)", len(texts), response.usage.total_tokens
    )
    return embeddings


async def embed_single(text: str, model: str | None = None) -> list[float]:
    """Embed a single text."""
    results = await embed_texts([text], model=model)
    return results[0]
