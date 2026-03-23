"""
SEC filing text parser — extract sections from 10-K, 10-Q, 8-K, DEF 14A.
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Common 10-K section patterns
SECTION_PATTERNS_10K = {
    "Item 1": r"(?:ITEM\s+1\.?\s*[-–—]?\s*BUSINESS)",
    "Item 1A": r"(?:ITEM\s+1A\.?\s*[-–—]?\s*RISK\s+FACTORS)",
    "Item 7": r"(?:ITEM\s+7\.?\s*[-–—]?\s*MANAGEMENT.S\s+DISCUSSION)",
    "Item 7A": r"(?:ITEM\s+7A\.?\s*[-–—]?\s*QUANTITATIVE)",
    "Item 8": r"(?:ITEM\s+8\.?\s*[-–—]?\s*FINANCIAL\s+STATEMENTS)",
}


class SECFilingParser:
    """Parse SEC filings and extract relevant sections."""

    def extract_sections(
        self, text: str, sections: list[str] | None = None
    ) -> dict[str, str]:
        """Extract named sections from a 10-K/10-Q filing."""
        if not sections:
            sections = list(SECTION_PATTERNS_10K.keys())

        results: dict[str, str] = {}
        for section_name in sections:
            pattern = SECTION_PATTERNS_10K.get(section_name)
            if not pattern:
                continue

            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.start()
                # Find the next ITEM header after this one
                next_item = re.search(r"ITEM\s+\d", text[match.end():], re.IGNORECASE)
                end = match.end() + next_item.start() if next_item else start + 50000
                section_text = text[start:end].strip()
                results[section_name] = section_text[:100000]  # cap at 100K chars

        logger.info("Extracted %d sections from filing", len(results))
        return results

    def extract_insider_data(self, form4_text: str) -> dict[str, Any]:
        """Parse Form 4 (insider transaction) data."""
        result: dict[str, Any] = {
            "is_purchase": False,
            "is_sale": False,
            "shares": 0,
            "price_per_share": 0.0,
            "total_value": 0.0,
            "owner_name": "",
            "relationship": "",
        }

        # Look for transaction code (P = purchase, S = sale)
        purchase_match = re.search(r"transactionCode.*?[\"'>]P[\"'<]", form4_text, re.IGNORECASE | re.DOTALL)
        sale_match = re.search(r"transactionCode.*?[\"'>]S[\"'<]", form4_text, re.IGNORECASE | re.DOTALL)

        if purchase_match:
            result["is_purchase"] = True
        if sale_match:
            result["is_sale"] = True

        # Extract share amounts
        shares_match = re.search(
            r"transactionShares.*?(\d[\d,]*\.?\d*)", form4_text, re.IGNORECASE | re.DOTALL
        )
        if shares_match:
            result["shares"] = float(shares_match.group(1).replace(",", ""))

        # Extract price
        price_match = re.search(
            r"transactionPricePerShare.*?(\d[\d,]*\.?\d*)", form4_text, re.IGNORECASE | re.DOTALL
        )
        if price_match:
            result["price_per_share"] = float(price_match.group(1).replace(",", ""))
            result["total_value"] = result["shares"] * result["price_per_share"]

        return result

    def extract_proxy_insider_ownership(self, def14a_text: str) -> float | None:
        """Extract insider ownership percentage from DEF 14A proxy statement."""
        patterns = [
            r"directors\s+and\s+(?:executive\s+)?officers.*?(\d+\.?\d*)\s*%",
            r"beneficial\s+ownership.*?(\d+\.?\d*)\s*%",
        ]
        for pat in patterns:
            match = re.search(pat, def14a_text, re.IGNORECASE | re.DOTALL)
            if match:
                pct = float(match.group(1))
                if 0 < pct < 100:
                    return pct / 100.0
        return None
