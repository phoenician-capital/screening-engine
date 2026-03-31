"""Growth Agent — Organic vs acquisition-driven analysis for selection."""

from __future__ import annotations

import logging

from src.scoring.agents.base_agent import AgentDecision, BaseAgent

logger = logging.getLogger(__name__)


class GrowthAgent(BaseAgent):
    """
    Stage 1 Selection Agent: Growth quality.
    Checks: Organic growth presence, flags acquisition-heavy companies.
    """

    def __init__(self):
        super().__init__("GrowthAgent")
        self.min_organic_growth = 0.03  # 3% organic growth required
        self.max_acquisition_intensity = 0.3  # >30% acquired growth is a flag

    async def evaluate(
        self,
        organic_revenue_growth: float | None = None,
        total_revenue_growth: float | None = None,
        major_acquisitions_3yr: int = 0,
        acquisition_spend: float | None = None,
        fcf: float | None = None,
    ) -> AgentDecision:
        """Evaluate growth quality (organic vs acquisition-driven)."""

        flags = []
        positives = []

        # Organic growth check
        if organic_revenue_growth is not None:
            if organic_revenue_growth >= self.min_organic_growth:
                positives.append(f"Organic growth {organic_revenue_growth:.1%}")
            else:
                flags.append(
                    f"Weak organic growth {organic_revenue_growth:.1%} (< {self.min_organic_growth:.0%})"
                )

        # Acquisition intensity check
        if (
            acquisition_spend is not None
            and total_revenue_growth is not None
            and total_revenue_growth > 0
        ):
            acquisition_intensity = acquisition_spend / (acquisition_spend + (total_revenue_growth * 1e9))
            if acquisition_intensity > self.max_acquisition_intensity:
                flags.append(
                    f"Acquisition-heavy growth {acquisition_intensity:.1%} > {self.max_acquisition_intensity:.0%}"
                )

        # Major acquisitions signal
        if major_acquisitions_3yr > 2:
            flags.append(f"Multiple major acquisitions ({major_acquisitions_3yr}) in 3 years")
        elif major_acquisitions_3yr > 0:
            positives.append(f"Strategic acquisitions ({major_acquisitions_3yr}) to complement organic")

        # FCF conversion of growth (quality check)
        if fcf is not None and fcf > 0:
            positives.append("Converting growth to free cash flow")
        elif fcf is not None and fcf <= 0:
            flags.append("Growth not converting to positive FCF")

        # Decision: pass if organic growth present OR strategic acquisitions with FCF
        passed = (
            (organic_revenue_growth is not None and organic_revenue_growth >= self.min_organic_growth)
            or (major_acquisitions_3yr > 0 and fcf is not None and fcf > 0)
        )

        reason = " | ".join(positives) if passed else " | ".join(flags) if flags else "Growth profile unclear"

        return AgentDecision(
            passed=passed,
            score=None,
            reason=reason,
            metadata={
                "organic_growth": organic_revenue_growth,
                "total_growth": total_revenue_growth,
                "major_acquisitions_3yr": major_acquisitions_3yr,
                "acquisition_intensity": acquisition_spend,
            },
        )
