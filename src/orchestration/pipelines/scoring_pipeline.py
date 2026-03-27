"""
Full scoring pipeline — ingestion → hard filter → score → rank → persist.
"""

from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)


def _build_feedback_context(recent_feedback) -> str:
    """Build analyst decision history string for the agent's learning."""
    if not recent_feedback:
        return "No analyst decisions recorded yet — this is an early run."

    accepted  = [f for f in recent_feedback if f.action == "research_now"]
    watched   = [f for f in recent_feedback if f.action == "watch"]
    rejected  = [f for f in recent_feedback if f.action == "reject"]

    lines = [f"Recent analyst decisions ({len(recent_feedback)} total, last 60 days):"]
    lines.append(f"  Research Now: {len(accepted)} | Watch: {len(watched)} | Pass: {len(rejected)}")

    if accepted:
        lines.append(f"  Companies selected for research: {', '.join(f.ticker for f in accepted[:10])}")

    if rejected:
        # Summarise reject reasons
        reasons: dict[str, int] = {}
        for f in rejected:
            r = f.reject_reason or "unspecified"
            reasons[r] = reasons.get(r, 0) + 1
        top_reasons = sorted(reasons.items(), key=lambda x: -x[1])[:5]
        lines.append("  Top reject reasons: " + "; ".join(f"{r} ({n}x)" for r, n in top_reasons))
        lines.append(f"  Recently passed: {', '.join(f.ticker for f in rejected[:8])}")

    lines.append("Use this to calibrate your scoring — reflect what Phoenician has revealed it values.")
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
    ) -> list[dict[str, Any]]:
        """
        Run the full scoring pipeline.
        If tickers not specified, scores all active companies.
        """
        # 1. Create scoring run record with full config snapshot
        from src.config.scoring_weights import load_scoring_weights
        from sqlalchemy import delete
        weights = load_scoring_weights()
        scoring_run = ScoringRun(
            run_type=run_type,
            config_snapshot=weights,
        )
        self.session.add(scoring_run)
        await self.session.flush()

        # Purge stale duplicate recommendations — keep only one row per ticker
        # (the one with the highest rank_score). This runs before adding new results.
        from sqlalchemy import delete as _delete_stmt, text as _text
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
        await self.session.flush()
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

                # 11. Final gate
                if not self.hard_filter.passes_min_score(fit_score):
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

        # Flush new recs to DB first
        await self.session.flush()

        # Re-rank ALL recommendations across all runs by rank_score descending
        # Deduplicate by ticker — keep only the highest rank_score per ticker
        from sqlalchemy import update as _update, select as _select

        all_recs = (await self.session.execute(
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
