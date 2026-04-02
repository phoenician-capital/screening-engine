"""Coordinates parallel company scoring with worker pool."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
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
        self.max_concurrent = 3  # Async semaphore limit — keep low to avoid LLM rate limits
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

            # 2. Selection pre-filter — eliminates low-quality companies before expensive LLM scoring
            on_progress(
                ScreeningProgress(
                    step="selection",
                    status="starting",
                    total_companies=len(companies),
                    elapsed_seconds=time.time() - t0,
                )
            )

            companies = await self._pre_filter_companies(companies, t0, on_progress)

            on_progress(
                ScreeningProgress(
                    step="selection",
                    status="complete",
                    total_companies=len(companies),
                    elapsed_seconds=time.time() - t0,
                )
            )

            # 3. Score surviving companies concurrently with semaphore
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
            if failed_companies:
                logger.info(f"Skipped {len(failed_companies)} companies (no metrics or hard-filter rejected)")

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

    async def _pre_filter_companies(
        self,
        companies: list[Company],
        t0: float,
        on_progress: Callable[[ScreeningProgress], None] | None = None,
    ) -> list[Company]:
        """
        Run the 5-agent SelectionPipeline on all companies and return only those
        that pass.

        Each company is evaluated in its own isolated DB session so a single DB error
        (e.g. a failed transaction on one company) cannot cascade and kill the rest.
        """
        engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Mutable counter shared with the per-agent callback
        _companies_done: list[int] = [0]

        def _agent_cb(ticker: str, agent_id: str) -> None:
            if on_progress:
                on_progress(
                    ScreeningProgress(
                        step="selection",
                        status="in_progress",
                        current_ticker=ticker,
                        current_agent=agent_id,
                        companies_scored=_companies_done[0],
                        total_companies=len(companies),
                        elapsed_seconds=time.time() - t0,
                    )
                )

        try:
            # ── Step 1: Bulk-load all metrics in a single session (fast, one round-trip) ──
            metrics_map: dict[str, object] = {}
            async with factory() as bulk_session:
                metric_repo = MetricRepository(bulk_session)

                async def _load_metric(company: Company):
                    try:
                        return company.ticker, await metric_repo.get_latest(company.ticker)
                    except Exception:
                        return company.ticker, None

                metric_results = await asyncio.gather(
                    *[_load_metric(c) for c in companies]
                )
                metrics_map = {
                    ticker: metric
                    for ticker, metric in metric_results
                    if metric is not None
                }

            # ── Step 2: Evaluate each company in its OWN isolated session ──────────────
            # Isolation guarantees that one company's DB error (failed transaction,
            # missing column, FK violation) cannot cascade to the others.
            results = []

            for company in companies:
                async with factory() as company_session:
                    try:
                        pipeline = CompanySelectionPipeline(company_session)
                        result = await pipeline.evaluate_company(
                            company,
                            metrics_map.get(company.ticker),
                            on_agent_progress=_agent_cb,
                        )
                        results.append(result)
                        _companies_done[0] += 1

                        status = "✓" if result.passed_selection else "✗"
                        logger.debug(
                            f"{status} {company.ticker}: "
                            f"{result.disqualification_reason or 'SELECTED'}"
                        )
                    except Exception as exc:
                        # Single-company failure — log and treat as passed (fail-open)
                        # so a code bug never silently removes a good company from scoring
                        logger.warning(
                            "Selection pipeline error for %s (%s: %s) — passing to scorer",
                            company.ticker, type(exc).__name__, exc,
                        )
                        from src.orchestration.pipelines.selection_pipeline import SelectionResult
                        results.append(SelectionResult(
                            ticker=company.ticker,
                            passed_selection=True,
                            filter_results={},
                            disqualification_reason=None,
                        ))
                        _companies_done[0] += 1

            # ── Step 3: Summarise ────────────────────────────────────────────────────
            passed_count = sum(1 for r in results if r.passed_selection)
            logger.info(
                "Selection pre-filter: %d/%d passed (%d rejected) in %.1fs",
                passed_count, len(companies), len(companies) - passed_count,
                time.time() - t0,
            )

            rejections = [r for r in results if not r.passed_selection and r.disqualification_reason]
            if rejections:
                first_reasons = [r.disqualification_reason.split(" | ")[0] for r in rejections]
                for reason, count in Counter(first_reasons).most_common(5):
                    logger.info("  Rejected %dx: %s", count, reason)

            passed_tickers = {r.ticker for r in results if r.passed_selection}
            return [c for c in companies if c.ticker in passed_tickers]

        except Exception as e:
            logger.error(
                "Selection pre-filter failed (%s: %s) — falling back to unfiltered list",
                type(e).__name__, e,
            )
            return companies

        finally:
            await engine.dispose()

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
