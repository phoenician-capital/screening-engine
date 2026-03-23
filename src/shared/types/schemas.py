"""
Pydantic schemas for data transfer between layers.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ── Company ──────────────────────────────────────────────────────
class CompanyData(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None
    country: str | None = None
    gics_sector: str | None = None
    gics_industry_group: str | None = None
    gics_industry: str | None = None
    gics_sub_industry: str | None = None
    market_cap_usd: float | None = None
    description: str | None = None
    website: str | None = None
    cik: str | None = None
    is_founder_led: bool | None = None
    founder_name: str | None = None


# ── Metrics ──────────────────────────────────────────────────────
class MetricData(BaseModel):
    ticker: str
    period_end: dt.date
    period_type: str = "annual"
    revenue: float | None = None
    gross_margin: float | None = None
    ebit_margin: float | None = None
    fcf: float | None = None
    fcf_yield: float | None = None
    capex_to_revenue: float | None = None
    net_debt: float | None = None
    net_debt_ebitda: float | None = None
    roic: float | None = None
    revenue_growth_yoy: float | None = None
    revenue_growth_3yr_cagr: float | None = None
    ev_ebit: float | None = None
    ev_fcf: float | None = None
    insider_ownership_pct: float | None = None
    analyst_count: int | None = None
    market_cap_usd: float | None = None


# ── Documents ────────────────────────────────────────────────────
class DocumentData(BaseModel):
    ticker: str
    doc_type: str
    source: str | None = None
    source_url: str | None = None
    accession_no: str | None = None
    title: str | None = None
    raw_text: str | None = None
    published_at: dt.datetime | None = None


# ── Scoring ──────────────────────────────────────────────────────
class CriterionScore(BaseModel):
    name: str
    score: float
    max_score: float
    weight: float
    evidence: str | None = None


class ScoringResult(BaseModel):
    ticker: str
    fit_score: float
    risk_score: float
    rank_score: float
    criteria: list[CriterionScore] = []
    disqualified: bool = False
    disqualify_reason: str | None = None


# ── Recommendations ──────────────────────────────────────────────
class Citation(BaseModel):
    ref: int
    doc_id: str
    doc_type: str
    url: str | None = None
    excerpt: str


class RecommendationData(BaseModel):
    id: uuid.UUID | None = None
    ticker: str
    fit_score: float
    risk_score: float
    rank_score: float
    rank: int | None = None
    memo_text: str | None = None
    citations: list[Citation] = []
    scoring_detail: dict[str, Any] = {}
    status: str = "pending"


# ── Feedback ─────────────────────────────────────────────────────
class FeedbackData(BaseModel):
    recommendation_id: uuid.UUID
    ticker: str
    action: str  # reject | watch | research_now
    reject_reason: str | None = None
    notes: str | None = None
    analyst_id: str | None = None


# ── Memo generation ──────────────────────────────────────────────
class MemoRequest(BaseModel):
    ticker: str
    recommendation_id: uuid.UUID
    max_chunks: int = 15


class MemoOutput(BaseModel):
    ticker: str
    memo_text: str
    citations: list[Citation]
    tokens_used: int = 0


# ── Generic tool response wrapper ────────────────────────────────
class ToolError(BaseModel):
    code: str  # RATE_LIMIT | NOT_FOUND | PARSE_FAILURE | TIMEOUT | AUTH_ERROR
    message: str
    retryable: bool = False


class ToolResponse(BaseModel):
    success: bool = True
    data: Any = None
    error: ToolError | None = None
