"""Red Flag Agent — Catches specific issues identified from analyst feedback."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.scoring.agents.base_agent import AgentDecision, BaseAgent
from src.db.repositories.base_repo import BaseRepository
from src.db.models.learned_patterns import SelectionLearnedPattern

logger = logging.getLogger(__name__)


class RedFlagAgent(BaseAgent):
    """
    Stage 1 Selection Agent: Red flag detection.
    Dynamically learns from analyst feedback (unsustainable buybacks, stock dilution, FCF issues).
    Checks both static red flags and learned patterns from recent feedback.
    """

    def __init__(self, session: AsyncSession | None = None):
        super().__init__("RedFlagAgent")
        self.session = session
        # Static red flag thresholds
        self.buyback_to_fcf_ratio_threshold = 1.0  # Buyback > 1.0x FCF is flag
        self.apic_to_re_growth_threshold = 1.5  # APIC growing faster than RE is flag
        self.fcf_to_capex_threshold = 0.5  # FCF < 50% of CapEx is flag

    async def evaluate(
        self,
        ticker: str,
        buyback_to_fcf_ratio: float | None = None,
        stock_dilution_rate: float | None = None,
        apic_growth_vs_re_growth: float | None = None,
        fcf: float | None = None,
        capex: float | None = None,
        net_debt_ebitda: float | None = None,
    ) -> AgentDecision:
        """Evaluate red flags — both static and learned."""

        flags = []
        applied_patterns = []

        # FIRST: Load learned patterns and adjust thresholds
        learned_patterns = {}
        if self.session and ticker:
            learned_patterns = await self._get_learned_patterns()

        # Helper to get dynamic threshold (learned or baseline)
        def _get_threshold(metric_name: str, baseline: float) -> tuple[float, bool]:
            """Get threshold for metric (learned or baseline).
            Returns (threshold, is_learned)
            """
            if metric_name in learned_patterns:
                pattern = learned_patterns[metric_name]
                # Only use learned threshold if confidence is high (>0.75)
                if pattern.get("confidence", 0) > 0.75:
                    return pattern.get("suggested_threshold", baseline), True
            return baseline, False

        # 1. Buyback sustainability check (DYNAMIC THRESHOLD)
        if buyback_to_fcf_ratio is not None:
            threshold, is_learned = _get_threshold("buyback_to_fcf_ratio", self.buyback_to_fcf_ratio_threshold)
            if buyback_to_fcf_ratio > threshold:
                source = f" (learned from analyst feedback)" if is_learned else ""
                flags.append(
                    f"Unsustainable buyback ratio {buyback_to_fcf_ratio:.1f}x FCF "
                    f"(> {threshold:.1f}x){source}"
                )
                if is_learned:
                    applied_patterns.append("buyback_to_fcf_ratio")

        # 2. Stock dilution check (DYNAMIC THRESHOLD)
        if stock_dilution_rate is not None:
            threshold, is_learned = _get_threshold("stock_dilution_rate", 0.02)
            if stock_dilution_rate > threshold:
                source = f" (learned)" if is_learned else ""
                flags.append(f"Stock dilution {stock_dilution_rate:.1%} annually (> {threshold:.1%}){source}")
                if is_learned:
                    applied_patterns.append("stock_dilution_rate")

        # 3. APIC growth vs Retained Earnings (DYNAMIC THRESHOLD)
        if apic_growth_vs_re_growth is not None:
            threshold, is_learned = _get_threshold("apic_vs_re_growth", self.apic_to_re_growth_threshold)
            if apic_growth_vs_re_growth > threshold:
                source = f" (learned)" if is_learned else ""
                flags.append(
                    f"APIC growing {apic_growth_vs_re_growth:.1f}x faster than retained earnings "
                    f"(> {threshold:.1f}x) — stock dilution concern{source}"
                )
                if is_learned:
                    applied_patterns.append("apic_vs_re_growth")

        # 4. FCF to CapEx check (DYNAMIC THRESHOLD)
        if fcf is not None and capex is not None and capex > 0:
            fcf_to_capex = fcf / capex
            threshold, is_learned = _get_threshold("fcf_to_capex", self.fcf_to_capex_threshold)
            if fcf_to_capex < threshold:
                source = f" (learned)" if is_learned else ""
                flags.append(
                    f"FCF/CapEx only {fcf_to_capex:.1%} (< {threshold:.0%}) "
                    f"— heavy capex intensity{source}"
                )
                if is_learned:
                    applied_patterns.append("fcf_to_capex")

        # 5. Leverage sustainability (DYNAMIC THRESHOLD)
        if net_debt_ebitda is not None:
            threshold, is_learned = _get_threshold("net_debt_ebitda", 5.0)
            if net_debt_ebitda > threshold:
                source = f" (learned)" if is_learned else ""
                flags.append(f"Excessive leverage {net_debt_ebitda:.1f}x ND/EBITDA (> {threshold:.1f}x){source}")
                if is_learned:
                    applied_patterns.append("net_debt_ebitda")

        passed = len(flags) == 0
        reason = " | ".join(flags) if flags else "No major red flags detected"

        return AgentDecision(
            passed=passed,
            score=None,
            reason=reason,
            metadata={
                "buyback_ratio": buyback_to_fcf_ratio,
                "stock_dilution": stock_dilution_rate,
                "apic_vs_re_growth": apic_growth_vs_re_growth,
                "fcf_to_capex": fcf / capex if (fcf and capex and capex > 0) else None,
                "leverage": net_debt_ebitda,
                "applied_learned_patterns": applied_patterns,  # Track which patterns were applied
                "learned_pattern_count": len(applied_patterns),
            },
        )

    async def _get_learned_patterns(self) -> dict:
        """
        Get all active learned patterns for red flag agent.
        Returns dict mapping metric_name → {confidence, suggested_threshold, ...}
        """
        if not self.session:
            return {}

        try:
            from sqlalchemy import select

            # Get active learned patterns for this agent
            stmt = select(SelectionLearnedPattern).where(
                SelectionLearnedPattern.agent_type == "red_flag",
                SelectionLearnedPattern.expires_at > datetime.utcnow(),
            )
            result = await self.session.execute(stmt)
            patterns = result.scalars().all()

            learned_dict = {}
            for pattern in patterns:
                metric = pattern.metric_name
                if metric:
                    # pattern_metadata may not exist in older DB schemas — access safely
                    meta = {}
                    try:
                        meta = pattern.pattern_metadata or {}
                    except Exception:
                        pass
                    learned_dict[metric] = {
                        "confidence": pattern.confidence,
                        "suggested_threshold": (
                            pattern.new_threshold.get("value")
                            if pattern.new_threshold
                            else None
                        ),
                        "original_threshold": (
                            pattern.old_threshold.get("value")
                            if pattern.old_threshold
                            else None
                        ),
                        "issue": meta.get("issue"),
                    }
            return learned_dict
        except Exception as e:
            # Rollback to prevent cascading transaction abort on the shared session
            try:
                await self.session.rollback()
            except Exception:
                pass
            logger.warning(f"Failed to load learned patterns: {e}")
            return {}
