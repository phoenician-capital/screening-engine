"""
Insider Conviction Worker.
Fetches latest Form 4 filings for companies in the universe,
detects clusters (2+ distinct insiders in window), sets is_cluster,
near_52wk_low, cluster_window_days on InsiderPurchase rows.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class InsiderConvictionWorker:
    """Refreshes insider cluster detection for all active companies."""

    def __init__(self, cluster_window_days: int = 30) -> None:
        self.cluster_window_days = cluster_window_days

    async def run_for_universe(self, session: AsyncSession) -> dict:
        from src.db.repositories.company_repo import CompanyRepository
        companies = await CompanyRepository(session).get_active()
        updated = 0
        for company in companies:
            try:
                result = await self.run_for_ticker(company.ticker, session)
                if result.get("clusters_detected"):
                    updated += 1
            except Exception as e:
                logger.warning("Insider conviction failed for %s: %s", company.ticker, e)
        return {"tickers_processed": len(companies), "clusters_detected": updated}

    async def run_for_ticker(
        self,
        ticker: str,
        session: AsyncSession,
        lookback_days: int | None = None,
    ) -> dict:
        from src.db.repositories.insider_repo import InsiderRepository
        window = lookback_days or self.cluster_window_days
        repo = InsiderRepository(session)
        purchases = list(await repo.get_for_ticker(ticker))

        if not purchases:
            return {"ticker": ticker, "clusters_detected": 0}

        cutoff = dt.date.today() - dt.timedelta(days=window)
        recent = [p for p in purchases if p.transaction_date >= cutoff and p.is_open_market]

        # Detect cluster
        distinct = {p.insider_name for p in recent}
        is_cluster = len(distinct) >= 2

        # Get price context for 52-wk low check
        current_price, week52_low = await self._get_price_context(ticker)

        for p in recent:
            p.is_cluster = is_cluster
            p.cluster_window_days = window
            if current_price and week52_low and week52_low > 0:
                pct_above = (current_price - week52_low) / week52_low
                p.near_52wk_low = pct_above <= 0.20

        await session.flush()
        return {"ticker": ticker, "clusters_detected": 1 if is_cluster else 0}

    async def _get_price_context(
        self, ticker: str
    ) -> tuple[float | None, float | None]:
        """Fetch current price and 52-week low from Yahoo Finance chart API."""
        try:
            import httpx
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with httpx.AsyncClient(timeout=10, headers=headers) as client:
                r = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                    params={"range": "1y", "interval": "1d"},
                )
                if r.status_code != 200:
                    return None, None
                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                current = meta.get("regularMarketPrice")
                low52 = meta.get("fiftyTwoWeekLow")
                return (float(current) if current else None, float(low52) if low52 else None)
        except Exception as e:
            logger.debug("Price context fetch failed for %s: %s", ticker, e)
            return None, None
