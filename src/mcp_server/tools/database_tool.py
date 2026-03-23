"""
MCP Tool: db.upsert_company / db.upsert_metrics / db.write_recommendation / db.write_feedback
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.feedback import Feedback
from src.db.models.metric import Metric
from src.db.models.recommendation import Recommendation
from src.db.repositories import (
    CompanyRepository,
    FeedbackRepository,
    RecommendationRepository,
)
from src.db.session import get_session
from src.mcp_server.middleware.error_handler import tool_endpoint
from src.shared.types import CompanyData, FeedbackData, MetricData

router = APIRouter()


@router.post("/upsert_company")
@tool_endpoint
async def upsert_company(
    data: CompanyData, session: AsyncSession = Depends(get_session)
):
    repo = CompanyRepository(session)
    company = await repo.upsert(data.model_dump())
    await session.commit()
    return {"ticker": company.ticker, "status": "upserted"}


@router.post("/upsert_metrics")
@tool_endpoint
async def upsert_metrics(
    data: MetricData, session: AsyncSession = Depends(get_session)
):
    metric = Metric(**data.model_dump())
    session.add(metric)
    await session.commit()
    return {"id": str(metric.id), "ticker": data.ticker, "status": "created"}


class WriteRecommendationRequest(BaseModel):
    ticker: str
    fit_score: float
    risk_score: float
    rank_score: float
    rank: int | None = None
    scoring_detail: dict | None = None
    scoring_run_id: str | None = None


@router.post("/write_recommendation")
@tool_endpoint
async def write_recommendation(
    data: WriteRecommendationRequest,
    session: AsyncSession = Depends(get_session),
):
    rec = Recommendation(
        ticker=data.ticker,
        fit_score=data.fit_score,
        risk_score=data.risk_score,
        rank_score=data.rank_score,
        rank=data.rank,
        scoring_detail=data.scoring_detail,
        scoring_run_id=uuid.UUID(data.scoring_run_id) if data.scoring_run_id else None,
    )
    session.add(rec)
    await session.commit()
    return {"id": str(rec.id), "ticker": data.ticker}


@router.post("/write_feedback")
@tool_endpoint
async def write_feedback(
    data: FeedbackData, session: AsyncSession = Depends(get_session)
):
    fb = Feedback(
        recommendation_id=data.recommendation_id,
        ticker=data.ticker,
        action=data.action,
        reject_reason=data.reject_reason,
        notes=data.notes,
        analyst_id=data.analyst_id,
    )
    session.add(fb)

    # Update recommendation status
    repo = RecommendationRepository(session)
    status_map = {
        "reject": "rejected",
        "watch": "watched",
        "research_now": "researching",
    }
    new_status = status_map.get(data.action)
    if new_status:
        await repo.update_status(data.recommendation_id, new_status)

    await session.commit()
    return {"id": str(fb.id), "action": data.action}
