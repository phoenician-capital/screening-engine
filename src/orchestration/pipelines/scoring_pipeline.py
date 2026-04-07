"""
Full scoring pipeline — ingestion → hard filter → score → rank → persist.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from src.config.settings import settings

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.recommendation import Recommendation
from src.db.models.scoring_run import ScoringRun
from src.db.repositories import (
    CompanyRepository,
    FeedbackRepository,
    MetricRepository,
    PortfolioRepository,
    RecommendationRepository,
)
from src.db.repositories.document_repo import DocumentRepository
from src.db.repositories.insider_repo import InsiderRepository
from src.extraction.claims import ClaimExtractor
from src.scoring.engine.fit_scorer import FitScorer
from src.scoring.engine.memo_generator import generate_memo
from src.scoring.engine.ranker import Ranker
from src.scoring.engine.risk_scorer import RiskScorer
from src.scoring.filters.hard_filters import HardFilterEngine
from src.shared.types import ScoringResult
from src.orchestration.pipelines.selection_pipeline import CompanySelectionPipeline

logger = logging.getLogger(__name__)


def _build_feedback_context(recent_feedback) -> str:
    """Build analyst decision history with verbatim notes for agent learning."""
    if not recent_feedback:
        return "No analyst decisions recorded yet — this is an early run."

    # Separate by action type
    accepted  = [f for f in recent_feedback if f.action == "research_now"]
    watched   = [f for f in recent_feedback if f.action == "watch"]
    rejected  = [f for f in recent_feedback if f.action == "reject"]

    # Get only notes with content (last 12 across all actions for context window)
    noted = [f for f in recent_feedback if f.notes and f.notes.strip()]
    noted_sorted = sorted(noted, key=lambda f: f.created_at, reverse=True)[:12]

    lines = [f"Recent analyst decisions ({len(recent_feedback)} total, last 60 days):"]
    lines.append(f"  RESEARCH NOW: {len(accepted)} | WATCH: {len(watched)} | PASS: {len(rejected)}")
    lines.append("")

    # Group noted feedback by action
    noted_by_action = {
        "research_now": [f for f in noted_sorted if f.action == "research_now"],
        "watch": [f for f in noted_sorted if f.action == "watch"],
        "reject": [f for f in noted_sorted if f.action == "reject"],
    }

    if noted_by_action["research_now"]:
        lines.append("  RESEARCH NOW decisions:")
        for f in noted_by_action["research_now"][:4]:
            note_preview = f.notes[:200].strip() if f.notes else ""
            if note_preview:
                lines.append(f"    [{f.ticker}] \"{note_preview}{'...' if len(f.notes) > 200 else ''}\"")

    if noted_by_action["watch"]:
        lines.append("  WATCH decisions:")
        for f in noted_by_action["watch"][:4]:
            note_preview = f.notes[:200].strip() if f.notes else ""
            if note_preview:
                lines.append(f"    [{f.ticker}] \"{note_preview}{'...' if len(f.notes) > 200 else ''}\"")

    if noted_by_action["reject"]:
        lines.append("  PASS decisions:")
        for f in noted_by_action["reject"][:4]:
            note_preview = f.notes[:200].strip() if f.notes else ""
            if note_preview:
                lines.append(f"    [{f.ticker}] \"{note_preview}{'...' if len(f.notes) > 200 else ''}\"")

    lines.append("")
    lines.append("Use these first-person analyst judgments to calibrate your scoring.")
    return "\n".join(lines)


# Hardcoded sector median fallbacks when DB has insufficient data
_SECTOR_MEDIANS_FALLBACK: dict[str, dict] = {
    "Technology":            {"median_gross_margin": 0.62, "median_roic": 0.14, "median_ev_ebit": 22.0},
    "Information Technology":{"median_gross_margin": 0.58, "median_roic": 0.16, "median_ev_ebit": 20.0},
    "Healthcare":            {"median_gross_margin": 0.55, "median_roic": 0.10, "median_ev_ebit": 18.0},
    "Health Care":           {"median_gross_margin": 0.55, "median_roic": 0.10, "median_ev_ebit": 18.0},
    "Consumer Defensive":    {"median_gross_margin": 0.35, "median_roic": 0.12, "median_ev_ebit": 16.0},
    "Consumer Staples":      {"median_gross_margin": 0.32, "median_roic": 0.11, "median_ev_ebit": 15.0},
    "Consumer Discretionary":{"median_gross_margin": 0.38, "median_roic": 0.10, "median_ev_ebit": 14.0},
    "Consumer Cyclical":     {"median_gross_margin": 0.38, "median_roic": 0.10, "median_ev_ebit": 14.0},
    "Industrials":           {"median_gross_margin": 0.28, "median_roic": 0.10, "median_ev_ebit": 14.0},
    "Communication Services":{"median_gross_margin": 0.50, "median_roic": 0.09, "median_ev_ebit": 16.0},
    "Materials":             {"median_gross_margin": 0.25, "median_roic": 0.09, "median_ev_ebit": 12.0},
}


class ScoringPipeline:
    """End-to-end scoring pipeline for the full company universe."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.company_repo = CompanyRepository(session)
        self.metric_repo = MetricRepository(session)
        self.feedback_repo = FeedbackRepository(session)
        self.rec_repo = RecommendationRepository(session)
        self.portfolio_repo = PortfolioRepository(session)
        self.insider_repo = InsiderRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.hard_filter = HardFilterEngine()
        self.fit_scorer = FitScorer()
        self.risk_scorer = RiskScorer()
        self.ranker = Ranker()
        self.last_run_id: uuid.UUID | None = None
        self.last_screen_number: int | None = None

    async def run(
        self,
        tickers: list[str] | None = None,
        run_type: str = "manual",
        bypass_data_check: bool = False,
        on_progress: callable = None,
    ) -> list[dict[str, Any]]:
        """
        Run the full scoring pipeline with coordinator.
        If tickers not specified, scores all active companies.

        Args:
            tickers: Optional list of specific tickers to score
            run_type: Type of run (manual, scheduled, portfolio_scan)
            bypass_data_check: Skip financial data validation for portfolio scans
            on_progress: Optional callback for progress updates (for SSE)

        Returns:
            List of scored companies as dicts
        """
        from src.config.scoring_weights import load_scoring_weights
        from src.orchestration.workers.screening_coordinator import ScreeningCoordinator
        from src.shared.scoring_state import ScreeningProgress
        from sqlalchemy import text as _text

        t0 = time.time()
        if on_progress is None:
            on_progress = lambda p: logger.info(str(p))

        try:
            # 1. Create scoring run record with full config snapshot
            weights = load_scoring_weights()
            await self.session.execute(
                _text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": 20260403},
            )
            next_screen_number = int((
                await self.session.execute(
                    _text("SELECT COALESCE(MAX(screen_number), 0) + 1 FROM scoring_runs")
                )
            ).scalar_one())
            scoring_run = ScoringRun(
                screen_number=next_screen_number,
                run_type=run_type,
                config_snapshot=weights,
            )
            self.session.add(scoring_run)
            await self.session.flush()
            scoring_run_id = scoring_run.id
            self.last_run_id = scoring_run_id
            self.last_screen_number = next_screen_number
            await self.session.commit()

            on_progress(ScreeningProgress(step="init", status="starting"))
            logger.info(
                "Created scoring run #%s (%s) — preserving historical recommendations",
                next_screen_number,
                scoring_run_id,
            )

            # 2. Get universe
            if tickers:
                companies = []
                for t in tickers:
                    c = await self.company_repo.get_by_ticker(t)
                    if c:
                        companies.append(c)
            else:
                companies = await self.company_repo.get_active()

            # Exclude portfolio holdings from universe screening — they are tracked separately
            if not tickers:
                portfolio_holdings = await self.portfolio_repo.get_active()
                portfolio_tickers  = {h.ticker for h in portfolio_holdings}
                before = len(companies)
                companies = [c for c in companies if c.ticker not in portfolio_tickers]
                excluded_count = before - len(companies)
                if excluded_count:
                    logger.info("Excluded %d portfolio holdings from universe screening", excluded_count)

            logger.info("Scoring pipeline: %d companies to evaluate", len(companies))
            on_progress(ScreeningProgress(
                step="discovery",
                status="complete",
                total_companies=len(companies),
                elapsed_seconds=time.time() - t0,
            ))

            # 3. Use coordinator for robust parallel scoring
            coordinator = ScreeningCoordinator()
            results = await coordinator.run_screening(
                companies=companies,
                scoring_run_id=scoring_run_id,
                on_progress=on_progress,
            )

        except Exception as e:
            logger.exception(f"Scoring pipeline error: {e}")
            on_progress(ScreeningProgress(
                step="error",
                status="failed",
                error_message=str(e),
                elapsed_seconds=time.time() - t0,
            ))
            raise

        try:
            # 4. Persist final ranking and metadata (using fresh session)
            async def _finalize():
                """Update scoring run with final stats and rank all recommendations."""
                from sqlalchemy import select as _select, update as _update, text as _text
                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
                from sqlalchemy.pool import NullPool

                # Use fresh session for finalization (avoid contamination)
                engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
                factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

                try:
                    async with factory() as session:
                        # Get all recommendations from this scoring run and re-rank globally
                        all_recs = (await session.execute(
                            _select(Recommendation)
                            .where(Recommendation.scoring_run_id == scoring_run_id)
                            .where(Recommendation.rank_score.isnot(None))
                            .where(Recommendation.rank_score > -50)
                            .order_by(Recommendation.rank_score.desc())
                        )).scalars().all()

                        # Deduplicate: keep only best score per ticker
                        seen_tickers: dict[str, Recommendation] = {}
                        for rec in all_recs:
                            if rec.ticker not in seen_tickers:
                                seen_tickers[rec.ticker] = rec
                            else:
                                rec.rank = None

                        deduped = list(seen_tickers.values())
                        deduped.sort(key=lambda r: float(r.rank_score or 0), reverse=True)

                        # Clear ranks only within this run
                        await session.execute(
                            _update(Recommendation)
                            .where(Recommendation.scoring_run_id == scoring_run_id)
                            .values(rank=None)
                        )

                        # Assign new ranks
                        for i, rec in enumerate(deduped, 1):
                            rec.rank = i

                        # Update scoring run stats
                        scoring_run = await session.get(ScoringRun, scoring_run_id)
                        if scoring_run:
                            scoring_run.tickers_scored = len(companies)
                            scoring_run.tickers_passed_filter = len(results)

                        await session.commit()

                        logger.info(
                            "Scoring complete for screen #%s: %d scored, %d ranked in %.1f seconds",
                            scoring_run.screen_number if scoring_run else next_screen_number,
                            len(companies),
                            len(deduped),
                            time.time() - t0,
                        )

                        on_progress(ScreeningProgress(
                            step="complete",
                            status="success",
                            total_ranked=len(deduped),
                            elapsed_seconds=time.time() - t0,
                        ))

                        return deduped

                finally:
                    await engine.dispose()

            ranked = await _finalize()

        except Exception as e:
            logger.exception(f"Ranking finalization error: {e}")
            raise

        return [
            {
                "rank": r.rank,
                "ticker": r.ticker,
                "fit_score": r.fit_score,
                "risk_score": r.risk_score,
                "rank_score": r.rank_score,
            }
            for r in ranked
        ]
