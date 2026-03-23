"""
SEC 8-K Auto-Scanner.
Daily: fetch all 8-K filings from last 24h for companies in our universe,
classify each using LLM, store as Document(doc_type='8k_signal'),
return tickers flagged for re-score.
"""
from __future__ import annotations

import datetime as dt
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TRIGGER_RESCORE_TYPES = {"ceo_change", "buyback_authorization", "restatement", "ma_announcement"}


class EightKScanner:

    async def scan_universe(
        self,
        session: AsyncSession,
        lookback_hours: int = 24,
    ) -> list[dict]:
        """
        Fetch 8-K filings filed in the last lookback_hours for all active companies.
        Returns list of {ticker, signal_type, sentiment, relevance_score, trigger_rescore, summary}.
        """
        from src.db.repositories.company_repo import CompanyRepository
        from src.db.repositories.document_repo import DocumentRepository
        from src.ingestion.sources.sec_edgar.client import SECEdgarClient

        companies = await CompanyRepository(session).get_active()
        cik_map = {c.ticker: c.cik for c in companies if c.cik}
        doc_repo = DocumentRepository(session)

        since = (dt.datetime.utcnow() - dt.timedelta(hours=lookback_hours)).strftime("%Y-%m-%d")
        results = []

        client = SECEdgarClient()

        for company in companies:
            cik = cik_map.get(company.ticker)
            if not cik:
                continue
            try:
                filings = await client.get_company_filings(cik, form_types=["8-K"], limit=5)
                for f in filings:
                    filed_at = f.get("filed_at") or f.get("filed") or ""
                    if filed_at and filed_at < since:
                        continue
                    accession = f.get("accession_no") or f.get("accession")
                    if not accession:
                        continue
                    if await doc_repo.exists_by_accession(accession):
                        continue
                    # Fetch filing text
                    filing_data = await client.fetch_filing(cik, accession, sections=None)
                    text = filing_data.get("text", "") or filing_data.get("raw_text", "")
                    if not text:
                        continue
                    # Classify
                    signal = await self.classify_8k(text[:12000], company.ticker, accession)
                    # Store
                    from src.db.models.document import Document
                    doc = Document(
                        ticker=company.ticker,
                        doc_type="8k_signal",
                        source="sec_edgar",
                        accession_no=accession,
                        title=f"{signal['signal_type']}: {signal['summary'][:120]}",
                        raw_text=text[:50000],
                        published_at=dt.datetime.utcnow(),
                        meta={
                            "signal_type": signal["signal_type"],
                            "sentiment": signal["sentiment"],
                            "relevance_score": signal["relevance_score"],
                            "trigger_rescore": signal["trigger_rescore"],
                            "summary": signal["summary"],
                        },
                    )
                    session.add(doc)
                    results.append({"ticker": company.ticker, **signal})
                    logger.info("8-K signal for %s: %s (relevance=%.2f)", company.ticker, signal["signal_type"], signal["relevance_score"])
            except Exception as e:
                logger.warning("8-K scan failed for %s: %s", company.ticker, e)

        if results:
            await session.flush()
        return results

    async def classify_8k(
        self,
        filing_text: str,
        ticker: str,
        accession_no: str,
    ) -> dict:
        from src.shared.llm.client_factory import get_llm_client
        from src.config.settings import settings
        from src.prompts.loader import load_prompt

        system_prompt = load_prompt("ingestion/classify_8k_system.j2")
        user_prompt = load_prompt("ingestion/classify_8k.j2", ticker=ticker, filing_text=filing_text[:10000])

        client = get_llm_client(settings.llm.extraction_model)
        try:
            response = await client.complete(
                system=system_prompt,
                user=user_prompt,
                max_tokens=300,
                temperature=0.1,
            )
            text = response.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            return {
                "signal_type": data.get("signal_type", "other"),
                "sentiment": data.get("sentiment", "neutral"),
                "relevance_score": float(data.get("relevance_score", 0.5)),
                "summary": data.get("summary", "")[:200],
                "trigger_rescore": bool(data.get("trigger_rescore", False)),
            }
        except Exception as e:
            logger.warning("8-K classification failed for %s %s: %s", ticker, accession_no, e)
            return {
                "signal_type": "other",
                "sentiment": "neutral",
                "relevance_score": 0.3,
                "summary": "Classification failed",
                "trigger_rescore": False,
            }
