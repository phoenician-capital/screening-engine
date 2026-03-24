"""
Universe expander — builds the full investable universe from EDGAR.

Strategy:
  1. Fetch all NYSE/Nasdaq companies from SEC EDGAR
  2. For each: pull XBRL financials + current price → compute market cap
  3. Filter to target market cap range
  4. Upsert company + metrics directly to DB (no separate ingest step)

This replaces the old LLM-based screener entirely.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.metric import Metric
from src.db.repositories import CompanyRepository, MetricRepository
from src.ingestion.sources.market_data.client import screen_universe_global

logger = logging.getLogger(__name__)


class UniverseExpander:
    """Build and expand the investable company universe from EDGAR."""

    def __init__(self, session: AsyncSession) -> None:
        self.session      = session
        self.company_repo = CompanyRepository(session)
        self.metric_repo  = MetricRepository(session)

    # ── Primary method: full EDGAR universe build ─────────────────────────────

    async def expand_via_screener(
        self,
        min_market_cap: float | None = None,
        max_market_cap: float | None = None,
        max_companies: int = 500,
        concurrency: int = 6,
    ) -> list[str]:
        """
        Pull companies from EDGAR, filter by market cap, upsert to DB.
        Returns list of tickers successfully added/updated.
        """
        from src.config.settings import settings

        min_cap = min_market_cap or settings.scoring.hard_min_market_cap
        max_cap = max_market_cap or settings.scoring.hard_max_market_cap

        logger.info("Starting EDGAR universe build: $%.0fM – $%.0fB, max %d companies",
                    min_cap / 1e6, max_cap / 1e9, max_companies)

        # Get tickers already in DB so we skip them and always find new ones
        existing = await self.company_repo.get_active(limit=10000)
        existing_tickers = {c.ticker for c in existing}

        results = await screen_universe_global(
            min_market_cap=min_cap,
            max_market_cap=max_cap,
            max_companies=max_companies,
            concurrency=concurrency,
            exclude_tickers=existing_tickers,
            include_intl=False,  # disabled until executor issue resolved on Render
        )

        # Store results using the existing session (already bound to this event loop)
        tickers_added: list[str] = []
        for r in results:
            ticker = r.get("company", {}).get("ticker", "?")
            try:
                co_info = r["company"]
                metrics = r["metrics"]

                await self.company_repo.upsert(co_info)
                await self.session.flush()
                metric = Metric(
                    ticker      = ticker,
                    period_end  = dt.date.today(),
                    period_type = "snapshot",
                    **{k: v for k, v in metrics.items() if k != "ticker"},
                )
                self.session.add(metric)
                await self.session.commit()
                tickers_added.append(ticker)
                logger.info("Stored %s", ticker)

            except Exception as e:
                import traceback
                logger.error("Failed to store %s: %s\n%s", ticker, e, traceback.format_exc())
                await self.session.rollback()

        logger.info("Universe build complete: %d companies stored", len(tickers_added))
        return tickers_added

    # ── Single ticker ingest ──────────────────────────────────────────────────

    async def ingest_ticker(self, ticker: str) -> bool:
        """Fetch and store a single ticker. Returns True on success."""
        from src.ingestion.sources.market_data.client import MarketDataClient
        client = MarketDataClient()
        try:
            co_info, metrics = await client.get_all_data(ticker)
            await self.company_repo.upsert(co_info)
            metric = Metric(
                ticker      = ticker,
                period_end  = dt.date.today(),
                period_type = "snapshot",
                **{k: v for k, v in metrics.items() if k != "ticker"},
            )
            self.session.add(metric)
            await self.session.commit()
            return True
        except Exception as e:
            logger.error("Failed to ingest %s: %s", ticker, e)
            await self.session.rollback()
            return False

    # ── Batch ticker ingest (for similarity/thematic) ────────────────────────

    async def ingest_new_tickers(self, tickers: list[str], batch_size: int = 10) -> int:
        """Ingest a list of specific tickers. Returns count of successes."""
        ingested = 0
        for ticker in tickers:
            ok = await self.ingest_ticker(ticker)
            if ok:
                ingested += 1
            await asyncio.sleep(0.2)
        return ingested

    # ── Similarity + thematic (LLM-assisted, for future use) ─────────────────

    async def expand_via_similarity(self, reference_ticker: str) -> list[str]:
        """Find companies similar to a reference ticker using LLM."""
        from src.ingestion.sources.market_data.client import _parse_tickers
        from src.prompts import load_prompt
        from src.shared.llm.client_factory import complete_with_search

        company = await self.company_repo.get_by_ticker(reference_ticker)
        if not company:
            return []

        prompt = load_prompt("discovery/similarity_search.j2",
                             company_name=company.name, ticker=reference_ticker)
        system = load_prompt("discovery/similarity_search_system.j2")
        text   = await complete_with_search(prompt, model="claude-sonnet-4-6",
                                            system=system, max_tokens=1000,
                                            temperature=0.2, max_searches=2)
        tickers = _parse_tickers(text)
        return await self.company_repo.get_tickers_not_in_db(tickers)

    async def expand_via_thematic(self, theme: str = "") -> list[str]:
        """Discover companies matching a free-text investment theme."""
        from src.ingestion.sources.market_data.client import _parse_tickers
        from src.prompts import load_prompt
        from src.shared.llm.client_factory import complete_with_search

        prompt = load_prompt("discovery/thematic_search.j2",
                             theme=theme or "founder-led quality compounders")
        system = load_prompt("discovery/thematic_search_system.j2")
        text   = await complete_with_search(prompt, model="claude-sonnet-4-6",
                                            system=system, max_tokens=1000,
                                            temperature=0.3, max_searches=2)
        tickers = _parse_tickers(text)
        return await self.company_repo.get_tickers_not_in_db(tickers)
