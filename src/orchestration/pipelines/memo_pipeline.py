"""
Memo generation pipeline — triggers memo creation for top-ranked companies.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories import CompanyRepository, MetricRepository, RecommendationRepository
from src.rag.generator.memo_generator import MemoGenerator
from src.shared.types import MemoOutput

logger = logging.getLogger(__name__)


class MemoPipeline:
    """Generate memos for the top N recommendations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rec_repo = RecommendationRepository(session)
        self.company_repo = CompanyRepository(session)
        self.metric_repo = MetricRepository(session)
        self.memo_gen = MemoGenerator(session)

    async def generate_top_memos(self, top_n: int = 20) -> list[MemoOutput]:
        """Generate memos for the top N pending recommendations."""
        recs = await self.rec_repo.get_top_ranked(limit=top_n, status="pending")

        outputs: list[MemoOutput] = []
        for rec in recs:
            if rec.memo_text:
                continue  # Already has memo

            company = await self.company_repo.get_by_ticker(rec.ticker)
            metrics = await self.metric_repo.get_latest(rec.ticker)

            if not company or not metrics:
                logger.warning("Missing data for %s, skipping memo", rec.ticker)
                continue

            company_data = {
                "name": company.name,
                "ticker": company.ticker,
                "country": company.country,
                "exchange": company.exchange,
            }

            metrics_data = {
                "market_cap_usd": float(metrics.market_cap_usd) if metrics.market_cap_usd else 0,
                "revenue_growth_yoy": float(metrics.revenue_growth_yoy) if metrics.revenue_growth_yoy else None,
                "gross_margin": float(metrics.gross_margin) if metrics.gross_margin else None,
                "ebit_margin": float(metrics.ebit_margin) if metrics.ebit_margin else None,
                "fcf_yield": float(metrics.fcf_yield) if metrics.fcf_yield else None,
                "roic": float(metrics.roic) if metrics.roic else None,
                "insider_ownership_pct": float(metrics.insider_ownership_pct) if metrics.insider_ownership_pct else None,
                "ev_ebit": float(metrics.ev_ebit) if metrics.ev_ebit else None,
                "ev_fcf": float(metrics.ev_fcf) if metrics.ev_fcf else None,
                "net_debt_ebitda": float(metrics.net_debt_ebitda) if metrics.net_debt_ebitda else None,
                "analyst_count": metrics.analyst_count,
            }

            scoring_detail = rec.scoring_detail or {}
            scoring_detail["fit_score"] = float(rec.fit_score)
            scoring_detail["risk_score"] = float(rec.risk_score)

            output = await self.memo_gen.generate(
                ticker=rec.ticker,
                recommendation_id=str(rec.id),
                company_data=company_data,
                metrics_data=metrics_data,
                scoring_detail=scoring_detail,
            )
            outputs.append(output)

            logger.info("Memo generated for %s", rec.ticker)

        return outputs
