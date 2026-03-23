"""
Transcript Analyzer.
Fetches last N earnings call transcripts per ticker via TranscriptClient,
runs LLM analysis to extract management quality signals,
stores result as Document(doc_type='transcript_analysis', meta={signals}).
"""
from __future__ import annotations

import datetime as dt
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TranscriptAnalyzer:

    async def analyze_company(
        self,
        ticker: str,
        session: AsyncSession,
        num_quarters: int = 3,
    ) -> dict:
        from src.ingestion.sources.transcripts.client import TranscriptClient
        from src.db.repositories.document_repo import DocumentRepository

        client = TranscriptClient()
        doc_repo = DocumentRepository(session)

        # Search for available quarters
        try:
            quarters = await client.search_transcripts(ticker)
        except Exception as e:
            logger.warning("Transcript search failed for %s: %s", ticker, e)
            return {"ticker": ticker, "error": str(e)}

        if not quarters:
            logger.info("No transcripts found for %s", ticker)
            return {"ticker": ticker, "quarters_found": 0}

        # Fetch up to num_quarters
        transcripts: list[dict] = []
        for q in quarters[:num_quarters]:
            try:
                t = await client.fetch(ticker, quarter=q)
                if t and t.get("text"):
                    transcripts.append({"quarter": q, "text": t["text"]})
            except Exception as e:
                logger.debug("Transcript fetch failed for %s %s: %s", ticker, q, e)

        if not transcripts:
            return {"ticker": ticker, "quarters_found": len(quarters), "transcripts_fetched": 0}

        # Extract signals
        signals = await self._extract_signals(ticker, transcripts)

        # Store as document
        from src.db.models.document import Document
        combined_text = "\n\n---\n\n".join(
            f"[{t['quarter']}]\n{t['text'][:5000]}" for t in transcripts
        )
        doc = Document(
            ticker=ticker,
            doc_type="transcript_analysis",
            source="perplexity",
            title=f"Transcript Analysis — {ticker} ({transcripts[0]['quarter']})",
            raw_text=combined_text[:50000],
            published_at=dt.datetime.utcnow(),
            meta={
                "signals": {
                    "guidance_direction": signals.get("guidance_direction"),
                    "management_tone": signals.get("management_tone"),
                    "margin_commentary": signals.get("margin_commentary"),
                    "competitive_positioning": signals.get("competitive_positioning"),
                },
                "summary": signals.get("summary", ""),
                "quarters_analyzed": signals.get("quarters_analyzed", []),
            },
        )
        session.add(doc)
        await session.flush()
        logger.info("Transcript analysis stored for %s", ticker)
        return {"ticker": ticker, "signals": signals, "quarters_analyzed": len(transcripts)}

    async def _extract_signals(self, ticker: str, transcripts: list[dict]) -> dict:
        from src.shared.llm.client_factory import get_llm_client
        from src.config.settings import settings
        from src.prompts.loader import load_prompt

        combined = "\n\n---\n\n".join(
            f"[{t['quarter']}]\n{t['text'][:4000]}" for t in transcripts
        )
        quarters_list = [t["quarter"] for t in transcripts]

        system_prompt = load_prompt("ingestion/analyze_transcript_system.j2")
        user_prompt = load_prompt(
            "ingestion/analyze_transcript.j2",
            ticker=ticker,
            transcript_text=combined,
            num_quarters=len(transcripts),
            quarters_list=quarters_list,
        )

        client = get_llm_client(settings.llm.primary_model)
        try:
            response = await client.complete(
                system=system_prompt,
                user=user_prompt,
                max_tokens=600,
                temperature=0.1,
            )
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            logger.warning("Transcript signal extraction failed for %s: %s", ticker, e)
            return {
                "guidance_direction": None,
                "management_tone": None,
                "margin_commentary": None,
                "competitive_positioning": None,
                "summary": "Extraction failed",
                "quarters_analyzed": [t["quarter"] for t in transcripts],
            }
