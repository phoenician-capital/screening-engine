"""Coordinates parallel company scoring with worker pool."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import select, text, update

from src.config.settings import settings
from src.db.models.company import Company
from src.db.models.recommendation import Recommendation
from src.db.repositories import (
    CompanyRepository,
    FeedbackRepository,
    MetricRepository,
    PortfolioRepository,
)
from src.orchestration.pipelines.selection_pipeline import CompanySelectionPipeline
from src.orchestration.workers.company_scorer import SingleCompanyScorer
from src.shared.scoring_state import ScreeningProgress
from src.shared.types import ScoringResult

logger = logging.getLogger(__name__)


class ScreeningCoordinator:
    """Orchestrates parallel company scoring with worker pool + batch processing."""

    def __init__(self):
        """Initialize coordinator."""
        self.scorer = SingleCompanyScorer()
        self.max_concurrent = 50  # Async semaphore limit
        self.batch_size = 20  # Commit batch size

    async def run_screening(
        self,
        companies: list[Company],
        scoring_run_id,
        on_progress: Callable[[ScreeningProgress], None],
    ) -> list[ScoringResult]:
        """
        Score all companies with worker pool.

        Args:
            companies: List of companies to score
            scoring_run_id: Parent scoring run ID
            on_progress: Callback for progress updates (for SSE)

        Returns:
            List of successful ScoringResults (sorted by rank_score descending)
        """
        t0 = time.time()
        results = []
        failed_companies = []

        try:
            # 1. Prepare shared context (once, not per-company)
            on_progress(
                ScreeningProgress(
                    step="init",
                    status="starting",
                    total_companies=len(companies),
                    elapsed_seconds=time.time() - t0,
                )
            )

            shared_context = await self._prepare_shared_context()

            logger.info(f"Starting screening of {len(companies)} companies")

            # 2. Score all companies concurrently with semaphore
            on_progress(
                ScreeningProgress(
                    step="scoring",
                    status="starting",
                    total_companies=len(companies),
                    elapsed_seconds=time.time() - t0,
                )
            )

            sem = asyncio.Semaphore(self.max_concurrent)

            async def _score_with_sem(company: Company):
                """Score company with semaphore lock."""
                async with sem:
                    try:
                        result = await self.scorer.score(
                            company, scoring_run_id, shared_context
                        )

                        if result:
                            results.append(result)
                            on_progress(
                                ScreeningProgress(
                                    step="scoring",
                                    status="in_progress",
                                    total_companies=len(companies),
                                    companies_scored=len(results),
                                    current_ticker=company.ticker,
                                    elapsed_seconds=time.time() - t0,
                                )
                            )
                            return result
                        else:
                            failed_companies.append(company)
                            return None

                    except Exception as e:
                        logger.exception(
                            f"Scorer pool error for {company.ticker}: {e}"
                        )
                        failed_companies.append(company)
                        return None

            # Score all companies concurrently
            await asyncio.gather(
                *[_score_with_sem(c) for c in companies], return_exceptions=False
            )

            logger.info(
                f"Scoring complete: {len(results)} succeeded, {len(failed_companies)} failed"
            )

            # 3. Retry failed companies (once) with fresh attempt
            if failed_companies:
                logger.info(f"Retrying {len(failed_companies)} failed companies...")

                on_progress(
                    ScreeningProgress(
                        step="retry",
                        status="starting",
                        total_companies=len(failed_companies),
                        companies_scored=len(results),
                        failed_companies=len(failed_companies),
                        elapsed_seconds=time.time() - t0,
                    )
                )

                retry_results = []
                for company in failed_companies:
                    async with sem:
                        try:
                            result = await self.scorer.score(
                                company, scoring_run_id, shared_context
                            )
                            if result:
                                results.append(result)
                                retry_results.append(company.ticker)
                                on_progress(
                                    ScreeningProgress(
                                        step="retry",
                                        status="in_progress",
                                        total_companies=len(failed_companies),
                                        companies_scored=len(retry_results),
                                        current_ticker=company.ticker,
                                        elapsed_seconds=time.time() - t0,
                                    )
                                )
                        except Exception as e:
                            logger.debug(f"Retry failed for {company.ticker}: {e}")

                logger.info(f"Retry complete: {len(retry_results)} recovered")

            # 4. Rank all successfully scored companies
            on_progress(
                ScreeningProgress(
                    step="ranking",
                    status="starting",
                    elapsed_seconds=time.time() - t0,
                )
            )

            # Sort by rank_score descending
            results.sort(key=lambda r: r.rank_score or 0, reverse=True)
            for i, result in enumerate(results, 1):
                result.rank = i

            on_progress(
                ScreeningProgress(
                    step="ranking",
                    status="complete",
                    total_ranked=len(results),
                    elapsed_seconds=time.time() - t0,
                )
            )

            logger.info(
                f"Screening complete: {len(results)} ranked in {time.time() - t0:.1f}s"
            )

            return results

        except Exception as e:
            logger.exception(f"Screening coordinator error: {e}")
            on_progress(
                ScreeningProgress(
                    step="error",
                    status="failed",
                    error_message=str(e),
                    elapsed_seconds=time.time() - t0,
                )
            )
            raise

    async def _prepare_shared_context(self) -> dict:
        """Prepare context shared across all company scoring."""
        engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with factory() as session:
                # Load portfolio context
                portfolio_repo = PortfolioRepository(session)
                portfolio_avg = await portfolio_repo.get_avg_metrics()

                # Load feedback context for learning
                feedback_repo = FeedbackRepository(session)
                recent_feedback = await feedback_repo.get_recent_feedback(days=60)

                from src.orchestration.pipelines.scoring_pipeline import (
                    _build_feedback_context,
                )

                feedback_context = _build_feedback_context(recent_feedback)

                # Pre-cache sector medians for common sectors
                metric_repo = MetricRepository(session)
                sector_medians_cache = {}
                for sector in [
                    "Technology",
                    "Healthcare",
                    "Consumer Discretionary",
                    "Industrials",
                ]:
                    try:
                        sector_medians_cache[sector] = (
                            await metric_repo.get_sector_medians(sector)
                        )
                    except Exception:
                        pass

                return {
                    "portfolio_avg": portfolio_avg,
                    "feedback_context": feedback_context,
                    "sector_medians_cache": sector_medians_cache,
                }

        finally:
            await engine.dispose()
