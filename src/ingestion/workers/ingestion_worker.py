"""
Ingestion worker — coordinates data pull from all sources for a company.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.company import Company
from src.db.models.document import Document
from src.db.models.metric import Metric
from src.db.repositories import CompanyRepository, DocumentRepository, MetricRepository
from src.ingestion.sources.market_data import MarketDataClient
from src.ingestion.sources.news import NewsClient
from src.ingestion.sources.sec_edgar import SECEdgarClient, SECFilingParser
from src.ingestion.sources.transcripts import TranscriptClient
from src.shared.types import CompanyData, MetricData

logger = logging.getLogger(__name__)


class IngestionWorker:
    """Pulls data for a single company across all sources."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.company_repo = CompanyRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.metric_repo = MetricRepository(session)
        self.market_client = MarketDataClient()
        self.sec_client = SECEdgarClient()
        self.sec_parser = SECFilingParser()
        self.transcript_client = TranscriptClient()
        self.news_client = NewsClient()

    async def ingest_company(self, ticker: str) -> dict:
        """Full ingestion pipeline for a single company."""
        logger.info("Starting ingestion for %s", ticker)
        results = {"ticker": ticker, "steps": {}}

        # 1 + 2. Market data → company profile + metrics (via FMP API)
        company_created = False
        try:
            company_info, raw_metrics = await self.market_client.get_all_data(ticker)
            await self.company_repo.upsert(company_info)
            company_created = True
            results["steps"]["company_profile"] = "ok"

            metric = Metric(
                ticker=ticker,
                period_end=datetime.now(timezone.utc).date(),
                period_type="snapshot",
                **{k: v for k, v in raw_metrics.items() if k != "ticker"},
            )
            self.session.add(metric)
            results["steps"]["metrics"] = "ok"
        except Exception as e:
            logger.error("Market data failed for %s: %s", ticker, e)
            results["steps"]["company_profile"] = f"error: {e}"
            results["steps"]["metrics"] = f"error: {e}"

        # Skip document steps if company record doesn't exist (FK constraint)
        if not company_created:
            existing = await self.company_repo.get_by_ticker(ticker)
            company_created = existing is not None

        if not company_created:
            logger.warning("Skipping SEC/news for %s — no company record", ticker)
            results["steps"]["sec_filings"] = "skipped (no company)"
            results["steps"]["news"] = "skipped (no company)"
            return results

        # 3. SEC filings
        try:
            company = await self.company_repo.get_by_ticker(ticker)
            if company and company.cik:
                filings = await self.sec_client.get_company_filings(
                    company.cik, form_types=["10-K", "10-Q", "8-K"], limit=5
                )
                for filing in filings:
                    if not await self.doc_repo.exists_by_accession(filing["accession_no"]):
                        doc = Document(
                            ticker=ticker,
                            doc_type=filing["form_type"],
                            source="sec_edgar",
                            accession_no=filing["accession_no"],
                            published_at=datetime.fromisoformat(filing["filing_date"]),
                        )
                        self.session.add(doc)
                results["steps"]["sec_filings"] = f"ok ({len(filings)} filings)"
        except Exception as e:
            logger.error("SEC filings failed for %s: %s", ticker, e)
            results["steps"]["sec_filings"] = f"error: {e}"

        # 4. Recent news
        try:
            articles = await self.news_client.search(
                query=f"{ticker} company news earnings",
                tickers=[ticker],
                limit=10,
            )
            for article in articles:
                doc = Document(
                    ticker=ticker,
                    doc_type="news",
                    source="perplexity",
                    title=article.get("title"),
                    source_url=article.get("url"),
                    raw_text=article.get("snippet"),
                    published_at=None,
                )
                self.session.add(doc)
            results["steps"]["news"] = f"ok ({len(articles)} articles)"
        except Exception as e:
            logger.error("News failed for %s: %s", ticker, e)
            results["steps"]["news"] = f"error: {e}"

        try:
            await self.session.flush()
        except Exception as e:
            logger.error("Flush failed for %s, rolling back: %s", ticker, e)
            await self.session.rollback()
            results["steps"]["flush"] = f"error: {e}"
        logger.info("Ingestion complete for %s: %s", ticker, results["steps"])
        return results

    async def ingest_batch(self, tickers: list[str]) -> list[dict]:
        """Ingest multiple companies sequentially with rate limiting.
        Each ticker is committed independently so one failure doesn't block others.
        """
        results = []
        for i, ticker in enumerate(tickers):
            try:
                result = await self.ingest_company(ticker)
                await self.session.commit()
            except Exception as e:
                logger.error("Batch ingest failed for %s: %s — rolling back and continuing", ticker, e)
                await self.session.rollback()
                result = {"ticker": ticker, "steps": {"error": str(e)}}
            results.append(result)
            if i < len(tickers) - 1:
                await asyncio.sleep(2)  # 2s between tickers to avoid Yahoo 429s
        return results
