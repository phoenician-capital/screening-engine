"""
Hard disqualifier filters — companies failing these are excluded entirely.
Round 1 filters per Phoenician Capital screening criteria.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config.scoring_weights import load_scoring_weights

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    passed: bool
    reason: str | None = None


class HardFilterEngine:
    """Apply binary pass/fail filters before scoring."""

    def __init__(self) -> None:
        self._reload()

    def _reload(self) -> None:
        self.weights = load_scoring_weights()
        hard = self.weights.get("hard_filters", {})
        self.excluded_sectors      = set(hard.get("excluded_gics_sectors", []))
        self.excluded_sub_industries = set(hard.get("excluded_gics_sub_industries", []))

        # Map GICS codes to text names AND include any text names directly in excluded_sectors
        _CODE_TO_NAME = {
            "10": "energy", "15": "materials", "20": "industrials",
            "25": "consumer discretionary", "30": "consumer staples",
            "35": "health care", "40": "financials", "45": "information technology",
            "50": "communication services", "55": "utilities", "60": "real estate",
        }
        # Build excluded names from codes AND from text entries in excluded_sectors
        self.excluded_sector_names: set[str] = set()
        for entry in self.excluded_sectors:
            if entry in _CODE_TO_NAME:
                self.excluded_sector_names.add(_CODE_TO_NAME[entry])
            else:
                # It's already a text name — add it directly
                self.excluded_sector_names.add(entry.lower())
        self.excluded_countries    = set(c.upper() for c in hard.get("excluded_countries", [
            "CN", "RU", "IR", "KP", "SY", "BY"
        ]))
        self.excluded_tickers      = set(t.upper() for t in hard.get("excluded_tickers", []))
        self.allowed_tier1         = set(c.upper() for c in hard.get("allowed_markets_tier1", [
            "US","GB","SE","NO","DK","FI","DE","NL","BE","CH","AU","CA","JP","SG","IL",
        ]))
        self.allowed_tier2         = set(c.upper() for c in hard.get("allowed_markets_tier2", [
            "PL","FR","IT","ES","AT","IE","NZ","HK",
        ]))
        self.tier2_min_score       = float(hard.get("tier2_min_score", 40))
        self.max_leverage          = float(hard.get("max_leverage", 5.0))
        self.min_gross_margin      = float(hard.get("min_gross_margin", 0.15))
        self.min_avg_daily_volume  = float(hard.get("min_avg_daily_volume_usd", 0))
        self.min_composite_score   = float(hard.get("min_composite_score", 20))
        self.require_profitable    = bool(hard.get("require_profitable", True))

        # Market cap bounds — from hard_filters or settings
        from src.config.settings import settings
        self.min_market_cap = float(
            hard.get("min_market_cap_usd", settings.scoring.min_market_cap)
        )
        self.max_market_cap = float(
            hard.get("max_market_cap_usd", settings.scoring.max_market_cap)
        )

    def check(
        self,
        gics_sector: str | None = None,
        gics_sub_industry: str | None = None,
        market_cap: float | None = None,
        net_debt_ebitda: float | None = None,
        gross_margin: float | None = None,
        country: str | None = None,
        avg_daily_volume: float | None = None,
        is_etf: bool = False,
        net_income: float | None = None,
        company_name: str | None = None,
        ticker: str | None = None,
        market_tier: int | None = None,
    ) -> FilterResult:

        # 0. Explicit ticker exclusion
        if ticker and ticker.upper() in self.excluded_tickers:
            return FilterResult(passed=False, reason=f"Explicitly excluded ticker: {ticker}")

        # 1. ETF / fund exclusion — objective fact, not a quality judgment
        if is_etf:
            return FilterResult(passed=False, reason="ETF or mutual fund excluded")

        # 2. Debt instruments — bonds, notes, preferred shares, warrants
        _DEBT_KEYWORDS = (
            "debenture", "subordinated", "notes due", "% fixed", "% senior",
            "preferred shares", "depositary shares", "warrant", "rights",
            "unit trust", "closed-end", "etf", "fund",
        )
        if company_name:
            name_lower = company_name.lower()
            for kw in _DEBT_KEYWORDS:
                if kw in name_lower:
                    return FilterResult(passed=False, reason=f"Debt/non-equity instrument: {kw}")

        # 3. Country exclusion — geopolitical hard block
        if country and country.upper() in self.excluded_countries:
            return FilterResult(passed=False, reason=f"Excluded country: {country}")

        # 4. Allowed market check
        _all_allowed = self.allowed_tier1 | self.allowed_tier2
        if country and _all_allowed and country.upper() not in _all_allowed:
            return FilterResult(passed=False, reason=f"Market not in allowed list: {country}")

        # 5. Market cap bounds — sizing mandate, objective fact
        if market_cap is not None:
            if market_cap < self.min_market_cap:
                return FilterResult(passed=False, reason=f"Market cap too small: ${market_cap/1e6:.0f}M")
            if market_cap > self.max_market_cap:
                return FilterResult(passed=False, reason=f"Market cap too large: ${market_cap/1e9:.1f}B")

        # All category/quality judgments are delegated to LLM agents
        return FilterResult(passed=True)

    def passes_min_score(self, composite_score: float, market_tier: int = 1) -> bool:
        """Final gate — Tier 2 markets must clear a higher bar than Tier 1."""
        threshold = self.tier2_min_score if market_tier == 2 else self.min_composite_score
        return composite_score >= threshold
