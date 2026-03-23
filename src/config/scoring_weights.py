"""
Loader for scoring weights YAML configuration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import settings

logger = logging.getLogger(__name__)

ScoringWeights = dict[str, Any]

_cache: ScoringWeights | None = None


def load_scoring_weights(force_reload: bool = False) -> ScoringWeights:
    """Load scoring weights from YAML. Cached after first load. Validates on load."""
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    path = settings.scoring.weights_file
    if not path.exists():
        logger.warning("Scoring weights file not found at %s, using defaults", path)
        _cache = _default_weights()
        return _cache

    with open(path, "r") as f:
        loaded = yaml.safe_load(f)

    # Validate category weights sum to 100
    cats = (loaded or {}).get("categories", {})
    if cats:
        total = sum(v.get("weight", 0) for v in cats.values())
        if abs(total - 100.0) > 1.0:
            logger.error(
                "scoring_weights.yaml: category weights sum to %.1f, expected 100. "
                "Using defaults to prevent corrupt scoring.", total
            )
            _cache = _default_weights()
            return _cache

    _cache = loaded
    logger.info("Loaded scoring weights v%s from %s", _cache.get("version"), path)
    return _cache


def _default_weights() -> ScoringWeights:
    """Fallback default weights if YAML missing."""
    return {
        "version": 0,
        "categories": {
            "founder_ownership": {"weight": 20},
            "business_quality": {"weight": 25},
            "unit_economics": {"weight": 20},
            "valuation_asymmetry": {"weight": 15},
            "information_edge": {"weight": 10},
            "scalability": {"weight": 10},
        },
        "ranking": {
            "fit_weight": 0.70,
            "risk_penalty_weight": 0.30,
        },
        "hard_filters": {
            "excluded_gics_sectors": ["10", "55"],
            "excluded_gics_sub_industries": ["35201010"],
            "max_leverage": 5.0,
            "min_gross_margin_2yr": 0.0,
        },
    }
