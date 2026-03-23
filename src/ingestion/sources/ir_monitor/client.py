"""
IR Monitor Client.
Uses Claude's built-in web search to fetch and parse IR pages.
This handles JS-rendered sites, multilingual pages, and paywalled content
better than raw httpx scraping.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class IRMonitorClient:

    async def scrape_ir_page(
        self,
        ticker: str,
        company_name: str,
        ir_url: str,
        events_url: str | None = None,
    ) -> list[dict]:
        """
        Use Claude web search to find and extract IR events for a company.
        Returns list of {event_type, title, url, event_date, raw_snippet}.
        """
        events = await self._search_ir_events(ticker, company_name, ir_url, events_url)
        # Deduplicate by title
        seen, unique = set(), []
        for e in events:
            key = (e.get("title", "") or "")[:80]
            if key and key not in seen:
                seen.add(key)
                unique.append(e)
        return unique

    async def _search_ir_events(
        self,
        ticker: str,
        company_name: str,
        ir_url: str,
        events_url: str | None,
    ) -> list[dict]:
        from src.shared.llm.client_factory import complete_with_search
        from src.config.settings import settings

        primary_url = events_url or ir_url

        prompt = f"""Search the investor relations page for {company_name} ({ticker}) at this URL: {primary_url}

Also check {ir_url} if needed.

Find all upcoming and recent investor relations events and documents, including:
- Earnings/results dates (quarterly, half-year, annual)
- Annual General Meetings (AGMs)
- Investor presentations or roadshows
- Annual reports or interim reports published
- Press releases about financial results
- Webcasts or conference calls

For each event found, output a JSON object. Return ONLY a JSON array.
If nothing is found, return an empty array [].

Format each item as:
{{
  "event_type": "<earnings_date|agm|presentation|annual_report|interim_report|press_release|webcast|other>",
  "title": "<event title in English>",
  "url": "<direct URL if available, null if not>",
  "event_date": "<ISO date YYYY-MM-DD if identifiable, null if not>",
  "raw_snippet": "<brief description, max 200 chars>"
}}

Return ONLY the JSON array, no other text."""

        try:
            response = await complete_with_search(
                prompt=prompt,
                model=settings.llm.primary_model,
                max_searches=1,
            )
            text = response.strip()
            # Strip markdown fences
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    if "[" in part and "{" in part:
                        text = part.strip()
                        if text.startswith("json"):
                            text = text[4:].strip()
                        break
            # Find JSON array in response
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]
            events = json.loads(text)
            if isinstance(events, list):
                valid = []
                for e in events:
                    if isinstance(e, dict) and e.get("title"):
                        valid.append({
                            "event_type": e.get("event_type", "other"),
                            "title": str(e.get("title", ""))[:500],
                            "url": e.get("url"),
                            "event_date": e.get("event_date"),
                            "raw_snippet": str(e.get("raw_snippet", ""))[:200],
                        })
                logger.info("IR monitor %s: found %d events via web search", ticker, len(valid))
                return valid[:20]
            return []
        except json.JSONDecodeError:
            logger.debug("IR monitor %s: JSON parse failed, response: %s", ticker, response[:200] if response else "empty")
            return []
        except Exception as e:
            logger.warning("IR monitor %s: web search failed: %s", ticker, e)
            return []
