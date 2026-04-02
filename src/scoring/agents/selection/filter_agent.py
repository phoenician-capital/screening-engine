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
        missing = []

        # Gross Margin — only reject if we have the data AND it's below threshold.
        # Missing gross_margin (common for intl companies via Yahoo timeseries) is not a reason
        # to reject — the LLM analyst will evaluate it via web search.
        if metrics.gross_margin is not None and metrics.gross_margin < self.min_gross_margin:
            failures.append(
                f"Gross margin {metrics.gross_margin:.1%} < {self.min_gross_margin:.0%}"
            )

        # ROIC — flag as missing but don't hard-reject (not all sources provide it)
        if metrics.roic is not None:
            if metrics.roic < self.min_roic:
                failures.append(
                    f"ROIC {metrics.roic:.1%} < {self.min_roic:.0%}"
                )

        # Revenue growth — flag as missing but don't hard-reject (calculated field, may lag)
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

        # Profitability gate — only reject if BOTH unprofitable AND low-margin
        # (high-gross-margin companies running losses are often high-quality reinvestors;
        #  the scoring step will penalise their profitability dimension appropriately)
        if metrics.net_income is not None and metrics.net_income < 0:
            gm = metrics.gross_margin
            if gm is None or gm < 0.50:
                # Low-margin loss-maker — genuinely unattractive, reject
                failures.append("Unprofitable with low margins: not a reinvestment-phase compounder")

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
