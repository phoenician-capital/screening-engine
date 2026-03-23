"""
Text processing utilities — chunking, cleaning, truncation.
"""

from __future__ import annotations

import re

from src.config.constants import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS


def clean_text(text: str) -> str:
    """Strip excessive whitespace and control characters."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()


def truncate(text: str, max_chars: int = 5000) -> str:
    """Truncate text to max_chars with ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """
    Split text into overlapping chunks by approximate token count.
    Uses word-based splitting with ~4 chars/token heuristic.
    """
    chars_per_token = 4
    chunk_chars = chunk_size * chars_per_token
    overlap_chars = overlap * chars_per_token

    text = clean_text(text)
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_chars

        # Try to break at sentence boundary
        if end < len(text):
            # Look for last period/newline in the chunk
            break_at = text.rfind(". ", start + chunk_chars // 2, end)
            if break_at == -1:
                break_at = text.rfind("\n", start + chunk_chars // 2, end)
            if break_at != -1:
                end = break_at + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap_chars
        if start >= len(text):
            break

    return chunks
