"""Filter Agent — Hard metrics gates for selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.scoring.agents.base_agent import AgentDecision, BaseAgent
from src.config.scoring_weights import load_scoring_weights

logger = logging.getLogger(__name__)


@dataclass
class FilterMetrics:
    """Required metrics for filter evaluation."""
    gross_margin: float | None = None
    roic: float | None = None
    revenue_growth_3yr: float | None = None
    net_debt_ebitda: float | None = None
    net_income: float | None = None


class FilterAgent(BaseAgent):
    """
    Stage 1 Selection Agent: Hard metrics gates.
    Checks: Gross Margin >= 30%, ROIC >= 8%, Growth >= 3%, Leverage <= 4.0x
    """

    def __init__(self):
        super().__init__("FilterAgent")
        self._reload()

    def _reload(self):
        """Load thresholds from config."""
        weights = load_scoring_weights()
        hard = weights.get("hard_filters", {})

        self.min_gross_margin = float(hard.get("min_gross_margin", 0.30))
        self.min_roic = float(hard.get("min_roic", 0.08))
        self.min_growth = float(hard.get("min_growth", 0.03))
        self.max_leverage = float(hard.get("max_leverage", 4.0))

    async def evaluate(self, metrics: FilterMetrics) -> AgentDecision:
        """Check if company passes hard metrics gates."""

        failures = []

        # Gross Margin check
        if metrics.gross_margin is not None:
            if metrics.gross_margin < self.min_gross_margin:
                failures.append(
                    f"Gross margin {metrics.gross_margin:.1%} < {self.min_gross_margin:.0%}"
                )

        # ROIC check
        if metrics.roic is not None:
            if metrics.roic < self.min_roic:
                failures.append(
                    f"ROIC {metrics.roic:.1%} < {self.min_roic:.0%}"
                )

        # Revenue growth check
        if metrics.revenue_growth_3yr is not None:
            if metrics.revenue_growth_3yr < self.min_growth:
                failures.append(
                    f"3Y growth {metrics.revenue_growth_3yr:.1%} < {self.min_growth:.0%}"
                )

        # Leverage check
        if metrics.net_debt_ebitda is not None:
            if metrics.net_debt_ebitda > self.max_leverage:
                failures.append(
                    f"Leverage {metrics.net_debt_ebitda:.1f}x > {self.max_leverage:.0f}x"
                )

        passed = len(failures) == 0
        reason = " | ".join(failures) if failures else "Passed all hard gates"

        return AgentDecision(
            passed=passed,
            score=None,
            reason=reason,
            metadata={
                "threshold_gm": self.min_gross_margin,
                "threshold_roic": self.min_roic,
                "threshold_growth": self.min_growth,
                "threshold_leverage": self.max_leverage,
            },
        )
