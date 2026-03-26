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

    # ── Claude pre-screen: send full universe to Claude, get best 100 back ──────

    async def _claude_prescreen(
        self,
        us_candidates: list[dict],
        intl_candidates: list[dict],
        target: int = 100,
        existing_tickers: set[str] | None = None,
    ) -> list[str]:
        """
        Send the full candidate universe to Claude with Phoenician Capital's
        mandate and portfolio context. Claude returns the best `target` tickers.
        This replaces brute-force FMP fetching of thousands of companies.
        """
        import json as _json
        from src.shared.llm.client_factory import complete_with_search
        from src.config.settings import settings
        from src.prompts.loader import load_prompt

        # Build candidate list — ticker + name + country/exchange for context
        # Shuffle to avoid geographic bias
        import random as _rng
        all_candidates = (
            [{"ticker": c["ticker"], "name": c["name"], "country": "US", "exchange": c.get("exchange","")} for c in us_candidates] +
            [{"ticker": c["ticker"], "name": c["name"], "country": c.get("country",""), "exchange": c.get("exchange","")} for c in intl_candidates]
        )
        _rng.shuffle(all_candidates)

        # Exclude already-in-DB tickers
        if existing_tickers:
            all_candidates = [c for c in all_candidates if c["ticker"] not in existing_tickers]

        # Format candidate list compactly — ticker | name | country
        candidate_lines = "\n".join(
            f"{c['ticker']:12s} | {c['name'][:40]:40s} | {c['country']}"
            for c in all_candidates
        )

        # Get portfolio for context
        portfolio = await self.company_repo.get_active(limit=10000)
        # Fall back to portfolio_holdings table
        holdings = []
        try:
            from sqlalchemy import text
            result = await self.session.execute(text("SELECT ticker, name, country FROM portfolio_holdings ORDER BY ticker"))
            holdings = [{"ticker": r[0], "name": r[1], "country": r[2]} for r in result.fetchall()]
        except Exception:
            holdings = [{"ticker": c.ticker, "name": c.name, "country": c.country} for c in portfolio[:20]]

        logger.info("Sending %d candidates to Claude for pre-screening (target: %d)...",
                    len(all_candidates), target)

        prompt = load_prompt(
            "discovery/claude_universe_screen.j2",
            portfolio=holdings,
            total_candidates=len(all_candidates),
            candidate_list=candidate_lines,
        )

        try:
            response = await complete_with_search(
                prompt=prompt,
                model=settings.llm.primary_model,
                max_tokens=8000,   # enough for 500 tickers in JSON
                temperature=0.1,
                max_searches=1,
            )
            # Parse JSON array from response
            text = response.strip()
            start = text.find("[")
            end   = text.rfind("]")
            if start != -1 and end != -1:
                tickers = _json.loads(text[start:end+1])
                tickers = [t.strip().upper() for t in tickers if isinstance(t, str)]
                logger.info("Claude pre-screen returned %d tickers (no cap applied)", len(tickers))
                # No artificial cap — Claude decides how many to select
                return tickers
        except Exception as e:
            logger.warning("Claude pre-screen failed: %s — falling back to random sample", e)

        # Fallback: broad random sample
        import random as _fallback_rng
        _fallback_rng.shuffle(all_candidates)
        return [c["ticker"] for c in all_candidates[:min(400, len(all_candidates))]]

    # ── Primary method: full EDGAR universe build ─────────────────────────────

    async def expand_via_screener(
        self,
        min_market_cap: float | None = None,
        max_market_cap: float | None = None,
        max_companies: int = 500,
        concurrency: int = 6,
    ) -> list[str]:
        """
        Pull companies from EDGAR + intl list, ask Claude to pre-select best
        100 candidates based on Phoenician mandate, then fetch financials for
        only those 100. Much faster than processing 2000+ companies blind.
        """
        from src.config.settings import settings
        import httpx

        min_cap = min_market_cap or settings.scoring.hard_min_market_cap
        max_cap = max_market_cap or settings.scoring.hard_max_market_cap

        logger.info("Starting smart universe build: $%.0fM – $%.0fB, max %d companies",
                    min_cap / 1e6, max_cap / 1e9, max_companies)

        # Step 1: Get existing tickers to exclude
        existing = await self.company_repo.get_active(limit=10000)
        existing_tickers = {c.ticker for c in existing}

        # Step 2: Get raw candidate lists (names only, no financials yet)
        from src.ingestion.sources.market_data.client import (
            _get_us_candidates, _get_intl_candidates, _cache_get, _cache_set,
            screen_universe_global
        )
        async with httpx.AsyncClient(timeout=20) as http_client:
            logger.info("Fetching US + international candidate lists...")
            us_raw   = await _get_us_candidates(http_client, min_cap, max_cap)
            intl_raw = await _get_intl_candidates(http_client, min_cap, max_cap)

        logger.info("Raw candidates: %d US + %d intl = %d total",
                    len(us_raw), len(intl_raw), len(us_raw) + len(intl_raw))

        # Step 3: Claude pre-screens the full universe — no artificial cap
        # Claude decides how many to select (target: 300-500)
        preselected = await self._claude_prescreen(
            us_candidates=us_raw,
            intl_candidates=intl_raw,
            target=500,   # upper safety limit only — Claude picks freely
            existing_tickers=existing_tickers,
        )
        logger.info("Claude pre-selected %d candidates for financial ingestion", len(preselected))

        # Step 4: Fetch financials only for pre-selected tickers
        # Build lookup maps
        us_map   = {c["ticker"]: c for c in us_raw}
        intl_map = {c["ticker"]: c for c in intl_raw}

        results = await screen_universe_global(
            min_market_cap=min_cap,
            max_market_cap=max_cap,
            max_companies=max_companies,
            concurrency=concurrency,
            exclude_tickers=existing_tickers,
            include_us=True,
            include_intl=True,
            preselected_tickers=preselected,
        )

        # Use psycopg2 (sync) for DB writes — avoids asyncpg event loop issues
        # after the long-running screen_universe_global call
        from src.config.settings import settings
        import psycopg2, psycopg2.extras, json

        tickers_added: list[str] = []
        try:
            conn = psycopg2.connect(
                host=settings.db.host, port=settings.db.port,
                dbname=settings.db.name, user=settings.db.user,
                password=settings.db.password,
                sslmode="require" if settings.db.ssl else "prefer",
                connect_timeout=15,
            )
            conn.autocommit = False
            cur = conn.cursor()

            for r in results:
                ticker = r.get("company", {}).get("ticker", "?")
                try:
                    co = r["company"]
                    m  = r["metrics"]

                    # Upsert company
                    cur.execute("""
                        INSERT INTO companies
                            (ticker, name, exchange, country, gics_sector, gics_industry_group,
                             gics_industry, gics_sub_industry, market_cap_usd, description,
                             website, cik, is_founder_led, founder_name, is_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (ticker) DO UPDATE SET
                            name=EXCLUDED.name, market_cap_usd=EXCLUDED.market_cap_usd,
                            gics_sector=EXCLUDED.gics_sector, is_active=TRUE,
                            updated_at=NOW()
                    """, (
                        co.get("ticker"), co.get("name","")[:255], co.get("exchange","")[:50],
                        co.get("country","")[:10], co.get("gics_sector","")[:100],
                        co.get("gics_industry_group","")[:100], co.get("gics_industry","")[:100],
                        co.get("gics_sub_industry","")[:100],
                        float(co["market_cap_usd"]) if co.get("market_cap_usd") else None,
                        co.get("description","")[:2000], co.get("website","")[:255],
                        co.get("cik"), co.get("is_founder_led"), co.get("founder_name"),
                        True,
                    ))

                    # Upsert metrics
                    def _f(v):
                        return float(v) if v is not None else None

                    cur.execute("""
                        INSERT INTO metrics
                            (ticker, period_end, period_type, revenue, gross_margin, ebit,
                             ebit_margin, net_income, fcf, roic, fcf_yield, revenue_growth_yoy,
                             net_debt_ebitda, total_assets, market_cap_usd, ev_ebit,
                             avg_daily_volume, analyst_count, insider_ownership_pct)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (ticker, period_end, period_type) DO UPDATE SET
                            revenue=EXCLUDED.revenue, gross_margin=EXCLUDED.gross_margin,
                            ebit=EXCLUDED.ebit, net_income=EXCLUDED.net_income,
                            fcf=EXCLUDED.fcf, roic=EXCLUDED.roic,
                            fcf_yield=EXCLUDED.fcf_yield,
                            revenue_growth_yoy=EXCLUDED.revenue_growth_yoy,
                            net_debt_ebitda=EXCLUDED.net_debt_ebitda,
                            total_assets=EXCLUDED.total_assets,
                            market_cap_usd=EXCLUDED.market_cap_usd
                    """, (
                        ticker, dt.date.today(), "snapshot",
                        _f(m.get("revenue")), _f(m.get("gross_margin")),
                        _f(m.get("ebit")), _f(m.get("ebit_margin")),
                        _f(m.get("net_income")), _f(m.get("fcf")),
                        _f(m.get("roic")), _f(m.get("fcf_yield")),
                        _f(m.get("revenue_growth_yoy")), _f(m.get("net_debt_ebitda")),
                        _f(m.get("total_assets")), _f(m.get("market_cap_usd")),
                        _f(m.get("ev_ebit")), _f(m.get("avg_daily_volume")),
                        m.get("analyst_count"), _f(m.get("insider_ownership_pct")),
                    ))

                    conn.commit()
                    tickers_added.append(ticker)
                    logger.info("Stored %s", ticker)

                except Exception as e:
                    conn.rollback()
                    logger.warning("Failed to store %s: %s", ticker, e)

            cur.close()
            conn.close()

        except Exception as e:
            logger.error("DB connection failed: %s", e)

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
