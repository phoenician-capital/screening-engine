"""
Full scoring pipeline — ingestion → hard filter → score → rank → persist.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

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

        # For manual runs: clear previous recommendations so Results shows only fresh results.
        # Scheduled runs (daily/weekly) preserve history for trend tracking.
        if run_type == "manual":
            await self.session.execute(delete(Recommendation))
            await self.session.flush()
            logger.info("Manual run — cleared previous recommendations")

        # 2. Get universe
        if tickers:
            companies = []
            for t in tickers:
                c = await self.company_repo.get_by_ticker(t)
                if c:
                    companies.append(c)
        else:
            companies = await self.company_repo.get_active()

        logger.info("Scoring pipeline: %d companies to evaluate", len(companies))

        # Load portfolio context once for all comparisons
        portfolio_avg = await self.portfolio_repo.get_avg_metrics()
        logger.info("Portfolio context: %d holdings loaded", portfolio_avg.get("holding_count", 0))

        results: list[ScoringResult] = []
        passed_filter = 0

        for company in companies:
            # 3. Get latest metrics
            metrics = await self.metric_repo.get_latest(company.ticker)
            if not metrics:
                logger.warning("No metrics for %s, skipping", company.ticker)
                continue

            # 3b. Skip companies with no usable financial data
            has_data = any([
                metrics.revenue is not None,
                metrics.ebit is not None,
                metrics.net_income is not None,
                metrics.total_assets is not None,
            ])
            if not has_data:
                logger.debug("Skipping %s — no financial data", company.ticker)
                continue

            # 4. Hard filter — full Round 1 criteria
            filter_result = self.hard_filter.check(
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
                continue

            passed_filter += 1

            # 5. Get sector medians for valuation comparison
            sector_medians = {}
            if company.gics_sector:
                sector_medians = await self.metric_repo.get_sector_medians(
                    company.gics_sector
                )

            # 6. Load insider cluster data and transcript signals
            cluster_purchases = list(
                await self.insider_repo.get_cluster_purchases_for_ticker(company.ticker, days=30)
            )
            transcript_doc = await self.doc_repo.get_latest_by_type(company.ticker, "transcript_analysis")
            transcript_signals = (
                transcript_doc.meta.get("signals") if transcript_doc and transcript_doc.meta else None
            )

            # 7. Fit score
            fit_score, fit_criteria = self.fit_scorer.score(
                company=company,
                metrics=metrics,
                sector_medians=sector_medians,
                claims=None,
                cluster_purchases=cluster_purchases,
                current_price=float(metrics.market_cap_usd / metrics.shares_outstanding)
                    if metrics.market_cap_usd and metrics.shares_outstanding and metrics.shares_outstanding > 0
                    else None,
                transcript_signals=transcript_signals,
            )

            # 7. Risk score
            risk_score, risk_criteria = self.risk_scorer.score(
                metrics=metrics,
                claims=None,
                country=company.country,
            )

            # 8. Feedback adjustment
            feedback_stats = await self.feedback_repo.count_by_action(company.ticker)
            rank_score = self.ranker.compute_rank_score(
                fit_score, risk_score, feedback_stats
            )

            all_criteria = [c.model_dump() for c in fit_criteria + risk_criteria]

            # 9. Generate investment memo with portfolio comparison
            memo_text, portfolio_comparison = generate_memo(
                company=company,
                metrics=metrics,
                fit_score=fit_score,
                risk_score=risk_score,
                fit_criteria=fit_criteria,
                risk_criteria=risk_criteria,
                portfolio_avg=portfolio_avg,
            )

            # 9b. Final gate — skip if fit score below minimum threshold
            if not self.hard_filter.passes_min_score(fit_score):
                logger.debug("Skipping %s — fit score %.1f below minimum", company.ticker, fit_score)
                continue

            results.append(ScoringResult(
                ticker=company.ticker,
                fit_score=fit_score,
                risk_score=risk_score,
                rank_score=rank_score,
                criteria=fit_criteria + risk_criteria,
            ))

            # 10. Check if this ticker was seeded by portfolio similarity (Redis)
            inspired_by = None
            try:
                import redis as _redis
                from src.config.settings import settings as _settings
                r = _redis.Redis.from_url(_settings.redis.url, decode_responses=True, socket_timeout=1)
                inspired_by = r.get(f"portfolio_similarity:{company.ticker}")
            except Exception:
                pass

            # 11. Persist recommendation
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

        # 10. Rank and apply top-N limit from config
        from src.config.scoring_weights import load_scoring_weights as _lsw
        top_n = int(_lsw().get("ranking", {}).get("top_n_results", 5))
        ranked = self.ranker.rank(results)[:top_n]
        for i, r in enumerate(ranked, 1):
            # Update rank on the recommendation we just created
            for rec_obj in self.session.new:
                if isinstance(rec_obj, Recommendation) and rec_obj.ticker == r.ticker:
                    rec_obj.rank = i
                    break

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
