"""Founder Agent — Alignment verification for selection."""

from __future__ import annotations

import logging

from src.scoring.agents.base_agent import AgentDecision, BaseAgent

logger = logging.getLogger(__name__)


class FounderAgent(BaseAgent):
    """
    Stage 1 Selection Agent: Founder/insider alignment.
    Checks: Founder ownership >= 5%, insider conviction signals.
    """

    def __init__(self):
        super().__init__("FounderAgent")
        self.min_founder_ownership = 0.05  # 5%
        self.min_insider_ownership = 0.10  # 10% for any insider group

    async def evaluate(
        self,
        founder_ownership: float | None = None,
        insider_ownership: float | None = None,
        founder_name: str | None = None,
        recent_insider_buys: int = 0,
    ) -> AgentDecision:
        """Evaluate founder/insider alignment."""

        flags = []
        positives = []

        # Founder ownership check
        if founder_ownership is not None:
            if founder_ownership >= self.min_founder_ownership:
                positives.append(
                    f"Founder owns {founder_ownership:.1%} (skin in game)"
                )
            else:
                flags.append(
                    f"Founder ownership only {founder_ownership:.1%} (< {self.min_founder_ownership:.0%})"
                )
        elif founder_name:
            # Founder name present but no ownership data
            flags.append(f"Founder identified ({founder_name}) but ownership % unknown")

        # Insider ownership check
        if insider_ownership is not None:
            if insider_ownership >= self.min_insider_ownership:
                positives.append(
                    f"Total insider ownership {insider_ownership:.1%} (strong alignment)"
                )
            else:
                flags.append(f"Insider ownership only {insider_ownership:.1%}")

        # Recent insider buys signal conviction
        if recent_insider_buys > 0:
            positives.append(f"Recent insider buying: {recent_insider_buys} transactions")

        no_data = (
            founder_ownership is None
            and insider_ownership is None
            and recent_insider_buys == 0
            and not founder_name
        )

        # Pass through when we have no data at all — the scoring stage will penalise
        # the alignment dimension if ownership can't be confirmed.
        # Only hard-reject when we have data AND it is clearly insufficient.
        passed = (
            no_data
            or (founder_ownership is not None and founder_ownership >= self.min_founder_ownership)
            or (insider_ownership is not None and insider_ownership >= self.min_insider_ownership)
            or recent_insider_buys > 0
        )

        if no_data:
            reason = "Alignment data unavailable — deferring to scoring stage"
        else:
            reason = " | ".join(positives) if passed else " | ".join(flags) if flags else "No alignment signals"

        return AgentDecision(
            passed=passed,
            score=None,
            reason=reason,
            metadata={
                "founder_ownership": founder_ownership,
                "insider_ownership": insider_ownership,
                "recent_insider_buys": recent_insider_buys,
            },
        )
