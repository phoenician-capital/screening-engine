"""
Learned patterns from analyst feedback for both selection and scoring teams.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class SelectionLearnedPattern(Base):
    __tablename__ = "selection_learned_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pattern_type: Mapped[str] = mapped_column(String(50))
    # "missed_red_flag", "miscalibration", "threshold_adjustment"

    agent_type: Mapped[str] = mapped_column(String(50))
    # "filter", "business_model", "founder", "growth", "red_flag"

    metric_name: Mapped[str | None] = mapped_column(String(100))
    # "buyback_ratio", "apic_growth", "clarity_score", etc.

    old_threshold: Mapped[dict | None] = mapped_column(JSON)
    new_threshold: Mapped[dict | None] = mapped_column(JSON)

    triggered_by_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id"), index=True
    )
    analyst_action: Mapped[str | None] = mapped_column(String(20))
    # "research_now", "watch", "reject"

    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    # How often does this pattern hold? 0-1

    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    # Companies filtered by this rule

    validation_count: Mapped[int] = mapped_column(Integer, default=0)
    # Companies that validated this (analyst agreed)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Auto-decay after 30 days

    pattern_metadata: Mapped[dict] = mapped_column(JSON, default=dict, name="pattern_metadata")
    # Additional context/reasoning

    def __repr__(self) -> str:
        return (
            f"<SelectionLearnedPattern {self.pattern_type} "
            f"({self.agent_type}) confidence={self.confidence:.2f}>"
        )


class ScoringLearnedPattern(Base):
    __tablename__ = "scoring_learned_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pattern_type: Mapped[str] = mapped_column(String(50))
    # "risk_factor", "dimension_weight", "red_flag"

    dimension: Mapped[str | None] = mapped_column(String(50))
    # "capital_returns", "growth_quality", "valuation", etc.

    pattern_data: Mapped[dict] = mapped_column(JSON)
    # Condition + action (e.g., {buyback_ratio_fcf: {threshold: 2.0, adjustment: -20}})

    triggered_by_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id"), index=True
    )
    analyst_action: Mapped[str | None] = mapped_column(String(20))
    # "research_now", "watch", "reject"

    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    # Pattern confidence 0-1

    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    # Times this pattern was applied

    validation_count: Mapped[int] = mapped_column(Integer, default=0)
    # Times analyst validated this pattern

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Auto-decay after 30-60 days

    pattern_metadata: Mapped[dict] = mapped_column(JSON, default=dict, name="pattern_metadata")

    def __repr__(self) -> str:
        return (
            f"<ScoringLearnedPattern {self.pattern_type} "
            f"({self.dimension}) confidence={self.confidence:.2f}>"
        )


class SelectionAgentDecision(Base):
    __tablename__ = "selection_agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_ticker: Mapped[str] = mapped_column(String(20), index=True)
    agent_type: Mapped[str] = mapped_column(String(50))
    # "filter", "business_model", "founder", "growth", "red_flag"

    passed_filter: Mapped[bool]
    # Did company pass this agent's filter?

    score: Mapped[float | None] = mapped_column(Float)
    # Optional: agent-specific score

    reason: Mapped[str | None] = mapped_column(String(500))
    # Why did it pass or fail?

    decision_data: Mapped[dict | None] = mapped_column(JSON)
    # Agent's full decision output

    screening_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Link to screening run

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        status = "✓" if self.passed_filter else "✗"
        return f"<SelectionAgentDecision {status} {self.company_ticker} ({self.agent_type})>"


class ScoringAgentDecision(Base):
    __tablename__ = "scoring_agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_ticker: Mapped[str] = mapped_column(String(20), index=True)
    agent_type: Mapped[str] = mapped_column(String(50))
    # "researcher", "scorer", "critic", "memo"

    decision_data: Mapped[dict] = mapped_column(JSON)
    # Agent's output (scores, findings, memo, etc.)

    was_correct: Mapped[bool | None] = mapped_column(default=None)
    # Did analyst agree with agent?

    screening_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Link to screening run

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ScoringAgentDecision {self.company_ticker} ({self.agent_type})>"
