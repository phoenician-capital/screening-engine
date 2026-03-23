"""
IR Monitor Worker.
Checks all portfolio companies' IR pages for new events.
Deduplicates against existing documents.
Returns new events for email digest.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IRMonitorWorker:

    async def run(self, session: AsyncSession) -> list[dict]:
        from src.db.repositories.portfolio_repo import PortfolioRepository
        from src.ingestion.sources.ir_monitor.client import IRMonitorClient

        portfolio_repo = PortfolioRepository(session)
        holdings = await portfolio_repo.get_active()

        # Ensure all portfolio tickers exist as company stubs so documents FK passes
        await self._ensure_company_stubs(holdings, session)

        client = IRMonitorClient()
        all_new_events: list[dict] = []
        active = [h for h in holdings if h.ir_url]

        # Process in batches of 3 concurrently to cut scan time to ~3-4 min
        batch_size = 3
        for i in range(0, len(active), batch_size):
            batch = active[i:i + batch_size]
            tasks = [self._check_holding(h, session, client) for h in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for holding, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning("IR monitor failed for %s: %s", holding.ticker, result)
                else:
                    all_new_events.extend(result)
                    logger.info("IR monitor %s: %d new events", holding.ticker, len(result))
            # Brief pause between batches
            if i + batch_size < len(active):
                await asyncio.sleep(2)

        return all_new_events

    async def _check_holding(
        self,
        holding,
        session: AsyncSession,
        client,
    ) -> list[dict]:
        from src.db.models.document import Document
        from src.db.repositories.document_repo import DocumentRepository

        doc_repo = DocumentRepository(session)

        events = await client.scrape_ir_page(
            ticker=holding.ticker,
            company_name=holding.name or holding.ticker,
            ir_url=holding.ir_url,
            events_url=holding.events_url,
        )

        new_events = []
        for event in events:
            title = event.get("title", "")[:500]
            url = event.get("url")

            # Deduplicate
            if await doc_repo.exists_by_title_or_url(holding.ticker, title, url):
                continue

            # Store
            published = None
            event_date_str = event.get("event_date")
            if event_date_str:
                try:
                    published = dt.datetime.fromisoformat(event_date_str)
                except Exception:
                    pass

            doc = Document(
                ticker=holding.ticker,
                doc_type="ir_event",
                source="ir_monitor",
                source_url=url,
                title=title,
                raw_text=event.get("raw_snippet", "")[:1000],
                published_at=published or dt.datetime.utcnow(),
                meta={
                    "event_type": event.get("event_type", "other"),
                    "event_date": event.get("event_date"),
                    "company_name": holding.name,
                },
            )
            session.add(doc)
            new_events.append({
                "ticker": holding.ticker,
                "company_name": holding.name or holding.ticker,
                "event_type": event.get("event_type", "other"),
                "title": title,
                "url": url,
                "event_date": event.get("event_date"),
            })

        if new_events:
            await session.flush()
        return new_events

    async def _ensure_company_stubs(self, holdings, session: AsyncSession) -> None:
        """Upsert minimal company records for portfolio holdings so FK on documents passes."""
        from sqlalchemy import select
        from src.db.models.company import Company

        for h in holdings:
            result = await session.execute(
                select(Company.ticker).where(Company.ticker == h.ticker).limit(1)
            )
            if result.scalar_one_or_none() is None:
                stub = Company(
                    ticker=h.ticker,
                    name=h.name or h.ticker,
                    exchange="",
                    country="",
                    gics_sector=h.sector or "",
                    is_active=False,  # not in screening universe — portfolio-only
                )
                session.add(stub)
        await session.flush()
