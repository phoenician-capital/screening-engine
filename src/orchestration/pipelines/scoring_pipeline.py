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
            scoring_run = ScoringRun(
                run_type=run_type,
                config_snapshot=weights,
            )
            self.session.add(scoring_run)
            await self.session.flush()
            scoring_run_id = scoring_run.id

            on_progress(ScreeningProgress(step="init", status="starting"))

            # Purge stale duplicate recommendations — keep only one row per ticker
            await self.session.execute(_text("""
                DELETE FROM recommendations
                WHERE id NOT IN (
                    SELECT DISTINCT ON (ticker) id
                    FROM recommendations
                    WHERE rank_score IS NOT NULL
                    ORDER BY ticker, rank_score DESC NULLS LAST
                )
                AND rank_score IS NOT NULL
            """))
            await self.session.commit()
            logger.info("Deduped recommendations — one row per ticker retained")

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

                        # Clear all ranks first
                        await session.execute(_update(Recommendation).values(rank=None))

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
                            "Scoring complete: %d scored, %d ranked in %.1f seconds",
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

    # ---- OLD IMPLEMENTATION (keeping for reference during transition) ----
    async def _run_old(
        self,
        tickers: list[str] | None = None,
        run_type: str = "manual",
        bypass_data_check: bool = False,
    ) -> list[dict[str, Any]]:
        """Legacy implementation - replaced by coordinator pattern."""
        # Load portfolio context once for all comparisons
        portfolio_avg = await self.portfolio_repo.get_avg_metrics()
        logger.info("Portfolio context: %d holdings loaded", portfolio_avg.get("holding_count", 0))

        # Load recent analyst decisions for feedback learning (last 60 days)
        recent_feedback = await self.feedback_repo.get_recent_feedback(days=60)
        feedback_context = _build_feedback_context(recent_feedback)
        logger.info("Feedback context: %d recent decisions loaded", len(recent_feedback))

        results: list[ScoringResult] = []
        passed_filter = 0
        sem = asyncio.Semaphore(20)  # 20 concurrent — agent calls are async, no blocking

        async def _score_one(company) -> None:
            async with sem:
                # 1.5. SELECTION TEAM PRE-FILTER (NEW)
                try:
                    selection_pipeline = CompanySelectionPipeline(self.session)
                    selection_result = await selection_pipeline.evaluate_company(company, None)

                    if not selection_result.passed_selection:
                        # Company rejected by selection team, skip scoring
                        results.append(ScoringResult(
                            ticker=company.ticker,
                            fit_score=0,
                            risk_score=100,
                            rank_score=-100,
                            disqualified=True,
                            disqualify_reason=f"Selection filter: {selection_result.disqualification_reason}",
                        ))
                        logger.debug(f"✗ {company.ticker}: {selection_result.disqualification_reason}")
                        return
                except Exception as e:
                    logger.warning(f"Selection pipeline error for {company.ticker}: {e}, continuing with normal scoring")
                    pass  # Continue with normal scoring if selection fails

                # 3. Get latest metrics
                metrics = await self.metric_repo.get_latest(company.ticker)
                if not metrics:
                    logger.warning("No metrics for %s, skipping", company.ticker)
                    return

                # 3b. Skip companies with no usable financial data (unless bypassed for portfolio scans)
                has_data = any([
                    metrics.revenue is not None,
                    metrics.ebit is not None,
                    metrics.net_income is not None,
                    metrics.total_assets is not None,
                ])
                if not has_data and not bypass_data_check:
                    logger.debug("Skipping %s — no financial data", company.ticker)
                    return

                # 4. Hard filter
                filter_result = self.hard_filter.check(
                    ticker=company.ticker,
                    gics_sector=company.gics_sector,
                    gics_sub_industry=company.gics_sub_industry,
                    market_cap=float(metrics.market_cap_usd) if metrics.market_cap_usd else None,
                    net_debt_ebitda=float(metrics.net_debt_ebitda) if metrics.net_debt_ebitda else None,
                    gross_margin=float(metrics.gross_margin) if metrics.gross_margin else None,
                    country=company.country,
                    avg_daily_volume=float(metrics.avg_daily_volume) if metrics.avg_daily_volume else None,
                    net_income=float(metrics.net_income) if metrics.net_income else None,
                    company_name=company.name,
                    market_tier=getattr(company, "market_tier", 1) or 1,
                )

                if not filter_result.passed:
                    results.append(ScoringResult(
                        ticker=company.ticker,
                        fit_score=0,
                        risk_score=100,
                        rank_score=-100,
                        disqualified=True,
                        disqualify_reason=filter_result.reason,
                    ))
                    return

                nonlocal passed_filter
                passed_filter += 1

                # 5. Sector medians
                sector_medians = {}
                if company.gics_sector:
                    sector_medians = await self.metric_repo.get_sector_medians(company.gics_sector)

                # 6. Insider + transcript signals
                cluster_purchases = list(
                    await self.insider_repo.get_cluster_purchases_for_ticker(company.ticker, days=30)
                )
                transcript_doc = await self.doc_repo.get_latest_by_type(company.ticker, "transcript_analysis")
                transcript_signals = (
                    transcript_doc.meta.get("signals") if transcript_doc and transcript_doc.meta else None
                )

                # 7. Fetch 5-year historical income statements for agent scoring
                historical = None
                try:
                    from src.ingestion.sources.market_data.client import _fetch_fmp_financials
                    import httpx as _httpx
                    from src.config.settings import settings as _settings
                    key = _settings.ingestion.fmp_api_key
                    if key:
                        async with _httpx.AsyncClient(timeout=15) as _hc:
                            r = await _hc.get(
                                "https://financialmodelingprep.com/stable/income-statement",
                                params={"symbol": company.ticker, "period": "annual",
                                        "limit": 5, "apikey": key}
                            )
                            if r.status_code == 200 and r.json():
                                historical = r.json()
                except Exception:
                    pass  # historical stays None — agent uses current year only

                # Enrich sector medians with fallback when DB has insufficient data
                enriched_sector_medians = dict(sector_medians) if sector_medians else {}
                if company.gics_sector and not enriched_sector_medians.get("median_gross_margin"):
                    fallback = _SECTOR_MEDIANS_FALLBACK.get(company.gics_sector, {})
                    enriched_sector_medians.update(fallback)

                # 8. Fit score (AI analyst agent — fully async, parallel)
                fit_score, fit_criteria = await self.fit_scorer.score(
                    company=company,
                    metrics=metrics,
                    sector_medians=enriched_sector_medians,
                    claims=None,
                    cluster_purchases=cluster_purchases,
                    current_price=float(metrics.market_cap_usd / metrics.shares_outstanding)
                        if metrics.market_cap_usd and metrics.shares_outstanding and metrics.shares_outstanding > 0
                        else None,
                    transcript_signals=transcript_signals,
                    historical=historical,
                    portfolio_avg=portfolio_avg,
                    feedback_context=feedback_context,
                )

                # 8. Risk score — use LLM risk score if agent ran, else Python
                llm_risk = next(
                    (c for c in fit_criteria if c.name == "llm_risk_score"), None
                )
                if llm_risk is not None and llm_risk.score > 0:
                    risk_score = min(100.0, max(0.0, llm_risk.score))
                    risk_criteria = [llm_risk]
                    logger.info("Risk score for %s: %.1f/100 (LLM)", company.ticker, risk_score)
                else:
                    risk_score, risk_criteria = self.risk_scorer.score(
                        metrics=metrics, claims=None, country=company.country,
                    )

                # 9. Rank score
                feedback_stats = await self.feedback_repo.count_by_action(company.ticker)
                rank_score = self.ranker.compute_rank_score(fit_score, risk_score, feedback_stats)

                all_criteria = [c.model_dump() for c in fit_criteria + risk_criteria]

                # 10. Memo
                memo_text, portfolio_comparison = await generate_memo(
                    company=company, metrics=metrics,
                    fit_score=fit_score, risk_score=risk_score,
                    fit_criteria=fit_criteria, risk_criteria=risk_criteria,
                    portfolio_avg=portfolio_avg,
                )

                # 11. Final gate — Tier 2 markets need a higher score
                _tier = getattr(company, "market_tier", 1) or 1
                if not self.hard_filter.passes_min_score(fit_score, market_tier=_tier):
                    logger.debug("Skipping %s — fit score %.1f below minimum", company.ticker, fit_score)
                    return

                results.append(ScoringResult(
                    ticker=company.ticker,
                    fit_score=fit_score,
                    risk_score=risk_score,
                    rank_score=rank_score,
                    criteria=fit_criteria + risk_criteria,
                ))

                # 12. Portfolio similarity badge
                inspired_by = None
                try:
                    import redis as _redis
                    r = _redis.Redis.from_url(settings.redis.url, decode_responses=True, socket_timeout=1)
                    inspired_by = r.get(f"portfolio_similarity:{company.ticker}")
                except Exception:
                    pass

                # 13. Persist recommendation
                rec = Recommendation(
                    ticker=company.ticker,
                    scoring_run_id=scoring_run.id,
                    fit_score=fit_score,
                    risk_score=risk_score,
                    rank_score=rank_score,
                    memo_text=memo_text,
                    portfolio_comparison=portfolio_comparison,
                    scoring_detail={"criteria": all_criteria},
                    inspired_by=inspired_by,
                )
                self.session.add(rec)

        await asyncio.gather(*[_score_one(c) for c in companies], return_exceptions=True)

        # Flush new recs to DB — with retry logic if transaction is aborted
        max_flush_retries = 2
        for attempt in range(max_flush_retries):
            try:
                await self.session.flush()
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Flush attempt 1 failed: {e}, retrying with rollback")
                    try:
                        await self.session.rollback()
                    except Exception:
                        pass
                else:
                    logger.error(f"Flush failed after {max_flush_retries} attempts, continuing with query")
                    raise

        # Re-rank ALL recommendations across all runs by rank_score descending
        # Deduplicate by ticker — keep only the highest rank_score per ticker
        from sqlalchemy import update as _update, select as _select

        try:
            all_recs = (await self.session.execute(
                _select(Recommendation)
                .where(Recommendation.rank_score.isnot(None))
                .where(Recommendation.rank_score > -50)
                .order_by(Recommendation.rank_score.desc())
            )).scalars().all()
        except Exception as e:
            logger.warning(f"Query error: {e}")
            all_recs = []

        # Deduplicate: keep only best score per ticker
        seen_tickers: dict[str, Recommendation] = {}
        for rec in all_recs:
            if rec.ticker not in seen_tickers:
                seen_tickers[rec.ticker] = rec
            else:
                # Mark duplicate as rank=None so it doesn't show
                rec.rank = None

        deduped = list(seen_tickers.values())
        deduped.sort(key=lambda r: float(r.rank_score or 0), reverse=True)

        # Clear all ranks first
        await self.session.execute(_update(Recommendation).values(rank=None))

        # Assign new ranks — no limit, show all qualifying companies
        for i, rec in enumerate(deduped, 1):
            rec.rank = i

        ranked = deduped  # for logging

        # 11. Update scoring run stats
        scoring_run.tickers_scored = len(companies)
        scoring_run.tickers_passed_filter = passed_filter

        await self.session.commit()

        logger.info(
            "Scoring complete: %d scored, %d passed filter, %d ranked",
            len(companies), passed_filter, len(ranked),
        )

        return [
            {
                "rank": i + 1,
                "ticker": r.ticker,
                "fit_score": r.fit_score,
                "risk_score": r.risk_score,
                "rank_score": r.rank_score,
            }
            for i, r in enumerate(ranked)
        ]
