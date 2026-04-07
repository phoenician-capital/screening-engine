"""Single company scorer with isolated database session."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config.settings import settings
from src.db.models.company import Company
from src.db.models.recommendation import Recommendation
from src.db.repositories import (
    FeedbackRepository,
    MetricRepository,
    PortfolioRepository,
)
from src.db.repositories.document_repo import DocumentRepository
from src.db.repositories.insider_repo import InsiderRepository
from src.scoring.engine.fit_scorer import FitScorer
from src.scoring.engine.memo_generator import generate_memo
from src.scoring.engine.ranker import Ranker
from src.scoring.engine.risk_scorer import RiskScorer
from src.scoring.filters.hard_filters import HardFilterEngine
from src.shared.exceptions import ScoringError
from src.shared.types import ScoringResult

logger = logging.getLogger(__name__)


class SingleCompanyScorer:
    """Score one company with its own isolated DB session."""

    def __init__(self):
        """Initialize scorer."""
        self.hard_filter = HardFilterEngine()
        self.fit_scorer = FitScorer()
        self.risk_scorer = RiskScorer()
        self.ranker = Ranker()

    async def score(
        self,
        company: Company,
        scoring_run_id: UUID,
        shared_context: dict,
    ) -> Optional[ScoringResult]:
        """
        Score one company with isolated session.

        Args:
            company: Company to score
            scoring_run_id: ID of parent scoring run
            shared_context: Dict with portfolio_avg, feedback_context, sector_medians_cache

        Returns:
            ScoringResult if successful, None if failed (logged but not raised)
        """
        # Create fresh session for this company only
        engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with factory() as session:
                # 1. Get metrics
                metric_repo = MetricRepository(session)
                metrics = await metric_repo.get_latest(company.ticker)

                if not metrics:
                    logger.debug(f"No metrics for {company.ticker}, skipping")
                    return None

                # 2. Skip companies with no usable financial data
                has_data = any(
                    [
                        metrics.revenue is not None,
                        metrics.ebit is not None,
                        metrics.net_income is not None,
                        metrics.total_assets is not None,
                    ]
                )
                if not has_data:
                    logger.debug(f"No financial data for {company.ticker}, skipping")
                    return None

                # 3. Hard filter
                filter_result = self.hard_filter.check(
                    ticker=company.ticker,
                    gics_sector=company.gics_sector,
                    gics_sub_industry=company.gics_sub_industry,
                    market_cap=float(metrics.market_cap_usd)
                    if metrics.market_cap_usd
                    else None,
                    net_debt_ebitda=float(metrics.net_debt_ebitda)
                    if metrics.net_debt_ebitda
                    else None,
                    gross_margin=float(metrics.gross_margin)
                    if metrics.gross_margin
                    else None,
                    country=company.country,
                    avg_daily_volume=float(metrics.avg_daily_volume)
                    if metrics.avg_daily_volume
                    else None,
                    net_income=float(metrics.net_income)
                    if metrics.net_income
                    else None,
                    company_name=company.name,
                    market_tier=getattr(company, "market_tier", 1) or 1,
                )

                if not filter_result.passed:
                    logger.debug(
                        f"Hard filter rejected {company.ticker}: {filter_result.reason}"
                    )
                    return None

                # 4. Get sector medians (cached or fetch)
                sector_medians = shared_context.get("sector_medians_cache", {}).get(
                    company.gics_sector, {}
                )
                if not sector_medians and company.gics_sector:
                    sector_medians = await metric_repo.get_sector_medians(
                        company.gics_sector
                    )

                # 5. Get insider/transcript data
                insider_repo = InsiderRepository(session)
                doc_repo = DocumentRepository(session)

                cluster_purchases = list(
                    await insider_repo.get_cluster_purchases_for_ticker(
                        company.ticker, days=30
                    )
                )
                transcript_doc = await doc_repo.get_latest_by_type(
                    company.ticker, "transcript_analysis"
                )
                transcript_signals = (
                    transcript_doc.meta.get("signals")
                    if transcript_doc and transcript_doc.meta
                    else None
                )

                # 6. Fetch 5-year historical metrics for trend analysis + DCF
                historical_metrics = await metric_repo.get_history(
                    company.ticker, period_type="annual", limit=5
                )
                historical: list[dict] | None = None
                if historical_metrics:
                    historical = []
                    for m in historical_metrics:
                        # Derive grossProfit from gross_profit or revenue * gross_margin
                        gross_profit = None
                        if m.gross_profit is not None:
                            gross_profit = float(m.gross_profit)
                        elif m.revenue is not None and m.gross_margin is not None:
                            gross_profit = float(m.revenue) * float(m.gross_margin)

                        historical.append({
                            "date": m.period_end.isoformat() if m.period_end else "",
                            "revenue":    float(m.revenue)    if m.revenue    is not None else None,
                            "grossProfit": gross_profit,
                            "ebit":       float(m.ebit)       if m.ebit       is not None else None,
                            "netIncome":  float(m.net_income) if m.net_income is not None else None,
                        })

                # Compute current price from market cap / shares
                current_price: float | None = None
                if (
                    metrics.market_cap_usd
                    and metrics.shares_outstanding
                    and float(metrics.shares_outstanding) > 0
                ):
                    current_price = float(metrics.market_cap_usd) / float(metrics.shares_outstanding)

                fit_score, fit_criteria = await self.fit_scorer.score(
                    company=company,
                    metrics=metrics,
                    sector_medians=sector_medians,
                    claims=None,
                    cluster_purchases=cluster_purchases,
                    current_price=current_price,
                    transcript_signals=transcript_signals,
                    historical=historical,
                    portfolio_avg=shared_context.get("portfolio_avg", {}),
                    feedback_context=shared_context.get("feedback_context", ""),
                )

                # 7. Risk score
                llm_risk = next(
                    (c for c in fit_criteria if c.name == "llm_risk_score"), None
                )
                if llm_risk is not None and llm_risk.score > 0:
                    risk_score = min(100.0, max(0.0, llm_risk.score))
                    risk_criteria = [llm_risk]
                else:
                    risk_score, risk_criteria = self.risk_scorer.score(
                        metrics=metrics, claims=None, country=company.country
                    )

                # 8. Rank score
                feedback_repo = FeedbackRepository(session)
                feedback_stats = await feedback_repo.count_by_action(company.ticker)
                rank_score = self.ranker.compute_rank_score(
                    fit_score, risk_score, feedback_stats
                )

                # 9. Final gate
                _tier = getattr(company, "market_tier", 1) or 1
                if not self.hard_filter.passes_min_score(fit_score, market_tier=_tier):
                    logger.debug(
                        f"Fit score {fit_score} below minimum for {company.ticker}"
                    )
                    return None

                all_criteria = [c.model_dump() for c in fit_criteria + risk_criteria]
                def _to_float(value):
                    return float(value) if value is not None else None

                company_snapshot = {
                    "name": company.name,
                    "exchange": company.exchange,
                    "country": company.country,
                    "sector": company.gics_sector,
                    "founder_led": company.is_founder_led,
                    "discovery_source": getattr(company, "discovery_source", None),
                    "market_tier": getattr(company, "market_tier", 1),
                    "market_cap_usd": _to_float(
                        metrics.market_cap_usd
                        if metrics.market_cap_usd is not None
                        else company.market_cap_usd
                    ),
                }
                metric_snapshot = {
                    "gross_margin": _to_float(metrics.gross_margin),
                    "roic": _to_float(metrics.roic),
                    "fcf_yield": _to_float(metrics.fcf_yield),
                    "revenue_growth_yoy": _to_float(metrics.revenue_growth_yoy),
                    "net_debt_ebitda": _to_float(metrics.net_debt_ebitda),
                    "ev_ebit": _to_float(metrics.ev_ebit),
                    "analyst_count": metrics.analyst_count,
                }

                # 10. Generate memo
                memo_text, portfolio_comparison = await generate_memo(
                    company=company,
                    metrics=metrics,
                    fit_score=fit_score,
                    risk_score=risk_score,
                    fit_criteria=fit_criteria,
                    risk_criteria=risk_criteria,
                    portfolio_avg=shared_context.get("portfolio_avg", {}),
                )

                # 11. Persist recommendation in THIS session
                rec = Recommendation(
                    ticker=company.ticker,
                    scoring_run_id=scoring_run_id,
                    fit_score=fit_score,
                    risk_score=risk_score,
                    rank_score=rank_score,
                    memo_text=memo_text,
                    portfolio_comparison=portfolio_comparison,
                    scoring_detail={
                        "criteria": all_criteria,
                        "company_snapshot": company_snapshot,
                        "metric_snapshot": metric_snapshot,
                    },
                )
                session.add(rec)

                # 12. Commit THIS company (isolated)
                await session.commit()

                logger.debug(
                    f"✓ {company.ticker}: fit={fit_score:.1f}, risk={risk_score:.1f}, rank={rank_score:.1f}"
                )

                return ScoringResult(
                    ticker=company.ticker,
                    fit_score=fit_score,
                    risk_score=risk_score,
                    rank_score=rank_score,
                    criteria=fit_criteria + risk_criteria,
                )

        except Exception as e:
            logger.exception(
                f"Error scoring {company.ticker}: {type(e).__name__}: {e}"
            )
            try:
                async with factory() as session:
                    await session.rollback()
            except Exception:
                pass
            return None

        finally:
            await engine.dispose()
