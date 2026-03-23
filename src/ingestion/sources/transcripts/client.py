"""
Earnings transcript fetcher — uses Perplexity deep-research to find + extract transcripts.
"""

from __future__ import annotations

import logging
from typing import Any

from src.prompts import load_prompt
from src.shared.llm.client_factory import complete

logger = logging.getLogger(__name__)

PERPLEXITY_MODEL = "sonar-deep-research"


class TranscriptClient:
    """Fetch and structure earnings call transcripts."""

    async def fetch(
        self,
        ticker: str,
        quarter: str,
    ) -> dict[str, Any]:
        """
        Fetch an earnings transcript for a given ticker/quarter.
        Uses Perplexity deep-research to locate and extract the transcript.
        """
        prompt = load_prompt(
            "ingestion/fetch_transcript.j2", ticker=ticker, quarter=quarter
        )
        system = load_prompt("ingestion/fetch_transcript_system.j2")

        text = await complete(
            prompt,
            model=PERPLEXITY_MODEL,
            system=system,
            max_tokens=8000,
            temperature=0.1,
        )

        logger.info("Fetched transcript for %s %s (%d chars)", ticker, quarter, len(text))

        return {
            "ticker": ticker,
            "quarter": quarter,
            "text": text,
            "source": "perplexity",
        }

    async def search_transcripts(
        self,
        ticker: str,
        limit: int = 4,
    ) -> list[dict[str, str]]:
        """List available transcript quarters for a ticker."""
        prompt = load_prompt(
            "ingestion/list_transcripts.j2", ticker=ticker, limit=limit
        )
        system = load_prompt("ingestion/list_transcripts_system.j2")

        text = await complete(
            prompt,
            model=PERPLEXITY_MODEL,
            system=system,
            max_tokens=200,
            temperature=0.1,
        )

        quarters = [
            line.strip()
            for line in text.strip().split("\n")
            if line.strip() and "Q" in line
        ]

        return [{"ticker": ticker, "quarter": q} for q in quarters[:limit]]
