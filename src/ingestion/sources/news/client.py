"""
News search client — Perplexity deep-research for real-time web-grounded news.
"""

from __future__ import annotations

import logging
from typing import Any

from src.prompts import load_prompt
from src.shared.llm.client_factory import complete

logger = logging.getLogger(__name__)

PERPLEXITY_MODEL = "sonar-deep-research"


class NewsClient:
    """Search for recent news and expert commentary via Perplexity."""

    async def search(
        self,
        query: str,
        tickers: list[str] | None = None,
        date_from: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for news articles matching a query.
        Returns structured list of articles with title, url, snippet.
        """
        prompt = load_prompt(
            "ingestion/news_search.j2",
            query=query,
            tickers=tickers or [],
            date_from=date_from,
            limit=limit,
        )
        system = load_prompt("ingestion/news_search_system.j2")

        text = await complete(
            prompt,
            model=PERPLEXITY_MODEL,
            system=system,
            max_tokens=4000,
            temperature=0.1,
        )

        articles = self._parse_articles(text)
        logger.info("News search '%s' returned %d articles", query[:50], len(articles))
        return articles[:limit]

    async def read_url(self, url: str) -> dict[str, str]:
        """Fetch and extract text content from a URL via Perplexity."""
        prompt = load_prompt("ingestion/web_read.j2", url=url)
        system = load_prompt("ingestion/web_read_system.j2")

        text = await complete(
            prompt,
            model=PERPLEXITY_MODEL,
            system=system,
            max_tokens=4000,
            temperature=0.1,
        )

        return {"url": url, "text": text}

    def _parse_articles(self, raw_text: str) -> list[dict[str, Any]]:
        """Parse structured article output from LLM."""
        articles = []
        current: dict[str, str] = {}

        for line in raw_text.split("\n"):
            line = line.strip()
            if line.startswith("TITLE:"):
                if current.get("title"):
                    articles.append(current)
                current = {"title": line[6:].strip()}
            elif line.startswith("URL:"):
                current["url"] = line[4:].strip()
            elif line.startswith("DATE:"):
                current["published_at"] = line[5:].strip()
            elif line.startswith("SNIPPET:"):
                current["snippet"] = line[8:].strip()
            elif line == "---":
                if current.get("title"):
                    articles.append(current)
                current = {}

        if current.get("title"):
            articles.append(current)

        return articles
