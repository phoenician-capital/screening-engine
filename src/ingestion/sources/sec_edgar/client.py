"""
SEC EDGAR API client — full-text search and filing retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config.settings import settings
from src.shared.utils import RateLimiter

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://efts.sec.gov/LATEST"
EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class SECEdgarClient:
    """Async client for the SEC EDGAR full-text search and filing APIs."""

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": settings.ingestion.sec_edgar_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self.limiter = RateLimiter(rate=settings.ingestion.sec_rate_limit_rps)

    async def search_filings(
        self,
        query: str,
        form_types: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Full-text search across EDGAR filings."""
        await self.limiter.acquire()

        params: dict[str, Any] = {
            "q": query,
            "dateRange": "custom",
            "startdt": date_from or "2020-01-01",
            "enddt": date_to or "2026-12-31",
            "forms": ",".join(form_types) if form_types else "",
        }

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(f"{EDGAR_BASE}/search-index", params=params)
            resp.raise_for_status()
            data = resp.json()

        hits = data.get("hits", {}).get("hits", [])[:limit]
        results = []
        for hit in hits:
            src = hit.get("_source", {})
            results.append({
                "ticker": src.get("display_names", [""])[0] if src.get("display_names") else "",
                "form_type": src.get("form_type", ""),
                "filing_date": src.get("file_date", ""),
                "accession_no": src.get("file_num", ""),
                "url": f"https://www.sec.gov/Archives/edgar/data/{src.get('entity_id', '')}/{src.get('file_num', '')}",
                "entity_name": src.get("entity_name", ""),
            })

        logger.info("EDGAR search '%s' returned %d results", query, len(results))
        return results

    async def fetch_filing(
        self,
        cik: str,
        accession_no: str,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch a specific filing by CIK and accession number."""
        await self.limiter.acquire()

        # Normalize accession number (remove dashes for URL)
        acc_clean = accession_no.replace("-", "")
        url = f"{EDGAR_ARCHIVES}/{cik}/{acc_clean}/{accession_no}.txt"

        async with httpx.AsyncClient(headers=self.headers, timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

        logger.info("Fetched filing %s for CIK %s (%d chars)", accession_no, cik, len(text))
        return {
            "cik": cik,
            "accession_no": accession_no,
            "text": text,
            "url": url,
        }

    async def get_company_filings(
        self,
        cik: str,
        form_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List recent filings for a company by CIK."""
        await self.limiter.acquire()

        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        results = []
        for i in range(min(len(forms), limit)):
            if form_types and forms[i] not in form_types:
                continue
            results.append({
                "form_type": forms[i],
                "filing_date": dates[i],
                "accession_no": accessions[i],
                "primary_document": primary_docs[i] if i < len(primary_docs) else "",
                "cik": cik,
            })
            if len(results) >= limit:
                break

        return results

    async def get_company_tickers_map(self) -> dict[str, str]:
        """Download CIK → ticker mapping."""
        await self.limiter.acquire()

        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(COMPANY_TICKERS_URL)
            resp.raise_for_status()
            data = resp.json()

        return {
            str(v["cik_str"]): v["ticker"]
            for v in data.values()
        }
