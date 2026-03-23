"""
Investment memo generator — RAG-powered, citation-tracked.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.repositories import RecommendationRepository
from src.prompts import load_prompt
from src.rag.retriever.vector_retriever import VectorRetriever
from src.shared.llm.client_factory import complete
from src.shared.types import Citation, MemoOutput

logger = logging.getLogger(__name__)


class MemoGenerator:
    """Generate investment memos using RAG retrieval + LLM synthesis."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.retriever = VectorRetriever(session)
        self.rec_repo = RecommendationRepository(session)

    async def generate(
        self,
        ticker: str,
        recommendation_id: str,
        company_data: dict[str, Any],
        metrics_data: dict[str, Any],
        scoring_detail: dict[str, Any],
        max_chunks: int = 15,
    ) -> MemoOutput:
        """
        Generate a full investment memo with citations.
        """
        # 1. Retrieve relevant chunks
        query = (
            f"{company_data.get('name', ticker)} business model "
            f"competitive advantage risks valuation management"
        )
        chunks = await self.retriever.search(
            query=query,
            ticker=ticker,
            top_k=max_chunks,
        )

        # 2. Build context block with numbered citations
        context_block = ""
        citations: list[Citation] = []
        for i, chunk in enumerate(chunks, 1):
            context_block += f"[{i}] {chunk['text'][:800]}\n\n"
            citations.append(Citation(
                ref=i,
                doc_id=chunk["metadata"].get("doc_id", ""),
                doc_type=chunk["metadata"].get("doc_type", ""),
                url=chunk["metadata"].get("source_url"),
                excerpt=chunk["text"][:200],
            ))

        # 3. Build DNA alignment section from scoring detail
        dna_section = self._format_dna_section(scoring_detail)

        # 4. Build financial snapshot
        financial_section = self._format_financials(metrics_data)

        # 5. Render prompt from Jinja2 templates
        system_prompt = load_prompt("memo/memo_system.j2")
        user_prompt = load_prompt(
            "memo/memo_user.j2",
            name=company_data.get("name", ticker),
            ticker=ticker,
            country=company_data.get("country", "N/A"),
            exchange=company_data.get("exchange", "N/A"),
            market_cap=f"{metrics_data.get('market_cap_usd', 0) / 1e6:.0f}",
            fit_score=f"{scoring_detail.get('fit_score', 0):.1f}",
            risk_score=f"{scoring_detail.get('risk_score', 0):.1f}",
            dna_section=dna_section,
            financial_section=financial_section,
            context_block=context_block,
        )

        # 6. Generate memo
        memo_text = await complete(
            user_prompt,
            model=settings.llm.memo_model,
            system=system_prompt,
            max_tokens=3000,
            temperature=0.3,
        )

        # 7. Save to recommendation
        import uuid
        rec_id = uuid.UUID(recommendation_id) if isinstance(recommendation_id, str) else recommendation_id
        await self.rec_repo.update_memo(
            rec_id,
            memo_text=memo_text,
            citations=[c.model_dump() for c in citations],
        )

        logger.info("Generated memo for %s (%d citations)", ticker, len(citations))

        return MemoOutput(
            ticker=ticker,
            memo_text=memo_text,
            citations=citations,
        )

    def _format_dna_section(self, scoring_detail: dict) -> str:
        """Format scoring criteria into DNA alignment summary."""
        lines = []
        criteria = scoring_detail.get("criteria", [])

        dna_map = {
            "founder_led": "Founder-Led / Owner-Operator",
            "insider_ownership": "Insider Alignment",
            "gross_margin": "Strong Unit Economics",
            "roic": "Capital Efficiency",
            "revenue_growth": "Scalable Growth",
            "fcf_positive_growing": "Cash Generation",
            "fcf_yield": "Cash Flow Yield",
            "ev_multiple_discount": "Valuation Asymmetry",
            "analyst_coverage": "Information Inefficiency",
            "tam_narrative": "Addressable Market",
            "pricing_power": "Competitive Moat",
        }

        for c in criteria:
            if isinstance(c, dict):
                name = c.get("name", "")
                label = dna_map.get(name, name)
                score = c.get("score", 0)
                max_s = c.get("max_score", 0)
                evidence = c.get("evidence", "")
                lines.append(f"- {label}: {score:.0f}/{max_s:.0f} — {evidence}")

        return "\n".join(lines) if lines else "No scoring detail available."

    def _format_financials(self, metrics: dict) -> str:
        """Format metrics into readable financial snapshot."""
        lines = []

        def _fmt(key: str, label: str, fmt_type: str = "pct"):
            val = metrics.get(key)
            if val is None:
                return
            if fmt_type == "pct":
                lines.append(f"- {label}: {val:.1%}")
            elif fmt_type == "x":
                lines.append(f"- {label}: {val:.1f}x")
            elif fmt_type == "n":
                lines.append(f"- {label}: {val}")
            elif fmt_type == "usd_m":
                lines.append(f"- {label}: ${val / 1e6:.0f}M")

        _fmt("revenue_growth_yoy", "Revenue Growth (YoY)", "pct")
        _fmt("gross_margin", "Gross Margin", "pct")
        _fmt("ebit_margin", "EBIT Margin", "pct")
        _fmt("fcf_yield", "FCF Yield", "pct")
        _fmt("roic", "ROIC", "pct")
        _fmt("insider_ownership_pct", "Insider Ownership", "pct")
        _fmt("ev_ebit", "EV/EBIT", "x")
        _fmt("ev_fcf", "EV/FCF", "x")
        _fmt("net_debt_ebitda", "Net Debt/EBITDA", "x")
        _fmt("analyst_count", "Analyst Coverage", "n")

        return "\n".join(lines) if lines else "Financial data not yet loaded."
