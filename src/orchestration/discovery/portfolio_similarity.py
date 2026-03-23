"""
Portfolio Similarity Expander.
For each active portfolio holding, runs expand_via_similarity()
and stores ticker→portfolio_seed mapping in Redis (TTL 24h).
The scoring pipeline reads Redis to tag recommendations with inspired_by.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REDIS_TTL_SECONDS = 86400  # 24 hours


class PortfolioSimilarityExpander:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        max_analogs_per_holding: int = 5,
    ) -> dict[str, list[str]]:
        """
        For each portfolio holding, find global analogs and store
        portfolio_similarity:{analog_ticker} → seed_ticker in Redis.
        Returns {portfolio_ticker: [analog_tickers_found]}.
        """
        from src.db.repositories.portfolio_repo import PortfolioRepository
        from src.orchestration.discovery.universe_expander import UniverseExpander
        import redis

        portfolio_repo = PortfolioRepository(self.session)
        holdings = await portfolio_repo.get_active()

        if not holdings:
            logger.info("No portfolio holdings — skipping similarity expansion")
            return {}

        expander = UniverseExpander(self.session)

        # Connect to Redis
        from src.config.settings import settings
        try:
            redis_client = redis.Redis.from_url(
                settings.redis.url, decode_responses=True, socket_timeout=5
            )
        except Exception as e:
            logger.warning("Redis unavailable for portfolio similarity: %s", e)
            redis_client = None

        results: dict[str, list[str]] = {}

        for holding in holdings:
            ticker = holding.ticker
            try:
                logger.info("Finding analogs for portfolio holding %s", ticker)
                analogs = await expander.expand_via_similarity(ticker)
                analogs = analogs[:max_analogs_per_holding]

                if analogs and redis_client:
                    pipe = redis_client.pipeline()
                    for analog in analogs:
                        pipe.setex(f"portfolio_similarity:{analog}", REDIS_TTL_SECONDS, ticker)
                    pipe.execute()

                results[ticker] = analogs
                logger.info("Found %d analogs for %s: %s", len(analogs), ticker, analogs)

                # Rate-limit LLM calls
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning("Portfolio similarity failed for %s: %s", ticker, e)
                results[ticker] = []

        total_analogs = sum(len(v) for v in results.values())
        logger.info(
            "Portfolio similarity complete: %d holdings, %d total analogs",
            len(holdings), total_analogs,
        )
        return results
