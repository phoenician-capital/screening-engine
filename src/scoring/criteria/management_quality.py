"""
Scoring criterion: Management Quality Signal (max 5 points).
Sourced from LLM-extracted earnings transcript signals.
Points freed from: pricing_power (5→2) + revenue_growth (5→3) = 5 pts freed.
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_management_quality(
    guidance_direction: str | None,
    management_tone: str | None,
    margin_commentary: str | None,
    competitive_positioning: str | None,
    cfg: dict | None = None,
) -> list[CriterionScore]:
    """
    guidance_direction:   raised=2, maintained=1, lowered/withdrawn=0
    management_tone:      confident=1, neutral=0.5, cautious/defensive=0
    margin_commentary:    expanding=1.5, stable=0.75, contracting=0
    competitive_positioning: strengthening=0.5, stable=0.25, weakening=0
    Max total: 5.0 pts
    """
    c = cfg or {}
    max_pts = float(c.get("max_points", 5.0))

    if max_pts == 0:
        return []

    score = 0.0
    parts: list[str] = []

    # Guidance (0–2)
    g = (guidance_direction or "").lower()
    if g == "raised":
        score += 2.0
        parts.append("guidance raised")
    elif g == "maintained":
        score += 1.0
        parts.append("guidance maintained")
    elif g in ("lowered", "withdrawn"):
        parts.append("guidance lowered")

    # Tone (0–1)
    t = (management_tone or "").lower()
    if t == "confident":
        score += 1.0
        parts.append("confident tone")
    elif t == "neutral":
        score += 0.5
        parts.append("neutral tone")
    elif t in ("cautious", "defensive"):
        parts.append(f"{t} tone")

    # Margins (0–1.5)
    m = (margin_commentary or "").lower()
    if m == "expanding":
        score += 1.5
        parts.append("expanding margins")
    elif m == "stable":
        score += 0.75
        parts.append("stable margins")
    elif m == "contracting":
        parts.append("contracting margins")

    # Competitive (0–0.5)
    cp = (competitive_positioning or "").lower()
    if cp == "strengthening":
        score += 0.5
        parts.append("strengthening position")
    elif cp == "stable":
        score += 0.25
        parts.append("stable position")
    elif cp == "weakening":
        parts.append("weakening position")

    if not any([guidance_direction, management_tone, margin_commentary, competitive_positioning]):
        evidence = "No transcript data available"
        score = 0.0
    else:
        evidence = "; ".join(parts) if parts else "Mixed signals"

    # Scale to configured max_points (default is already 5)
    scaled = score * (max_pts / 5.0)

    return [CriterionScore(
        name="management_quality_signal",
        score=min(max_pts, scaled),
        max_score=max_pts,
        weight=1.0,
        evidence=evidence,
    )]
