"""
Claim / signal extractor — finds qualitative signals in text using LLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config.settings import settings
from src.prompts import load_prompt
from src.shared.llm.client_factory import complete

logger = logging.getLogger(__name__)

CLAIM_TYPES = [
    "pricing_power",
    "founder_mention",
    "insider_buying",
    "tam_expansion",
    "recurring_revenue",
    "international_expansion",
    "competitive_moat",
    "customer_concentration_risk",
    "management_change",
    "accounting_concern",
    "regulatory_risk",
    "catalyst",
]


class ClaimExtractor:
    """Extract qualitative investment signals from document text."""

    async def extract(
        self,
        text: str,
        claim_types: list[str] | None = None,
        doc_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract claims from text.
        Returns list of claim dicts.
        """
        types_to_use = claim_types or CLAIM_TYPES
        truncated = text[:25000]

        prompt = load_prompt(
            "extraction/extract_claims.j2",
            claim_types=types_to_use,
            text=truncated,
        )
        system = load_prompt("extraction/extract_claims_system.j2")

        raw_response = await complete(
            prompt,
            model=settings.llm.extraction_model,
            system=system,
            max_tokens=2000,
            temperature=0.1,
        )

        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            claims = json.loads(cleaned)
            if not isinstance(claims, list):
                claims = []
        except json.JSONDecodeError:
            logger.warning("Failed to parse claims for doc %s", doc_id)
            claims = []

        # Validate and enrich
        valid_claims = []
        for claim in claims:
            if (
                isinstance(claim, dict)
                and claim.get("type") in CLAIM_TYPES
                and claim.get("text")
            ):
                claim["doc_id"] = doc_id
                valid_claims.append(claim)

        logger.info(
            "Extracted %d claims from doc %s", len(valid_claims), doc_id
        )
        return valid_claims
