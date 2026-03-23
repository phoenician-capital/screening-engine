"""
LLM-powered financial data extractor from filing text.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config.settings import settings
from src.prompts import load_prompt
from src.shared.llm.client_factory import complete

logger = logging.getLogger(__name__)


class FinancialParser:
    """Extract structured financial metrics from filing/document text using LLM."""

    async def parse(self, text: str, doc_id: str | None = None) -> dict[str, Any]:
        """
        Parse financial data from raw text.
        Returns structured metrics dict.
        """
        truncated = text[:30000]

        prompt = load_prompt("extraction/parse_financials.j2", text=truncated)
        system = load_prompt("extraction/parse_financials_system.j2")

        raw_response = await complete(
            prompt,
            model=settings.llm.extraction_model,
            system=system,
            max_tokens=1000,
            temperature=0.0,
        )

        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse extraction response for doc %s", doc_id)
            result = {"confidence": 0.0, "error": "parse_failure"}

        if doc_id:
            result["doc_id"] = doc_id

        logger.info(
            "Extracted financials for doc %s (confidence: %.2f)",
            doc_id,
            result.get("confidence", 0),
        )
        return result
