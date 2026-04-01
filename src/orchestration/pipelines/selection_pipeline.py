"""
Selection Pipeline — Stage 1 of two-stage screening.
Filters 1000 companies → ~40-50 quality candidates using Selection Team agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select as _select, func as _func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.company import Company
from src.db.models.metric import Metric
from src.db.models.learned_patterns import SelectionAgentDecision
from src.db.models.insider_purchase import InsiderPurchase
from src.db.repositories import MetricRepository
from src.scoring.agents.selection.filter_agent import FilterAgent, FilterMetrics
from src.scoring.agents.selection.business_model_agent import BusinessModelAgent
from src.scoring.agents.selection.founder_agent import FounderAgent
from src.scoring.agents.selection.growth_agent import GrowthAgent
from src.scoring.agents.selection.red_flag_agent import RedFlagAgent

logger = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    """Result of selection pipeline for one company."""
    ticker: str
    passed_selection: bool
    filter_results: dict  # {agent_type: decision}
    disqualification_reason: str | None = None


class CompanySelectionPipeline:
    """Orchestrate 5 selection agents to filter companies."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.metric_repo = MetricRepository(session)
        self.filter_agent = FilterAgent()
        self.business_model_agent = BusinessModelAgent()
        self.founder_agent = FounderAgent()
        self.growth_agent = GrowthAgent()
        self.red_flag_agent = RedFlagAgent(session)

    async def select_candidates(
        self, companies: list[Company], metrics_map: dict[str, Metric]
    ) -> list[SelectionResult]:
        """
        Run all companies through selection pipeline.
        Returns list of SelectionResult with pass/fail decisions.
        """
        results = []

        for company in companies:
            result = await self.evaluate_company(company, metrics_map.get(company.ticker))
            results.append(result)

            # Log result
            status = "✓" if result.passed_selection else "✗"
            logger.debug(
                f"{status} {company.ticker}: {result.disqualification_reason or 'SELECTED'}"
            )

        # Summary logging
        passed_count = sum(1 for r in results if r.passed_selection)
        logger.info(
            f"Selection complete: {passed_count}/{len(companies)} "
            f"({passed_count/len(companies)*100:.1f}%) passed to scoring"
        )

        return results

    async def evaluate_company(
        self, company: Company, metric: Metric | None
    ) -> SelectionResult:
        """Evaluate one company through all 5 selection agents."""

        filter_results = {}

        # LOAD ACTUAL DATA FROM DATABASE
        if not metric:
            metric = await self._load_company_metrics(company.ticker)

        # Load founder/insider/acquisition data
        founder_ownership, insider_ownership, recent_insider_buys = await self._load_alignment_data(company.ticker)
        major_acquisitions_3yr, acquisition_spend = await self._load_acquisition_data(company.ticker)
        organic_revenue_growth = await self._calculate_organic_growth(company.ticker)

        logger.debug(
            f"{company.ticker}: founder_own={founder_ownership}, insider_own={insider_ownership}, "
            f"recent_buys={recent_insider_buys}, acquisitions={major_acquisitions_3yr}"
        )

        # 1. FILTER AGENT — Hard metrics gates
        filter_decision = await self.filter_agent.evaluate(
            metrics=FilterMetrics(
                gross_margin=metric.gross_margin if metric else None,
                roic=metric.roic if metric else None,
                revenue_growth_3yr=metric.revenue_growth_3yr if metric else None,
                net_debt_ebitda=metric.net_debt_ebitda if metric else None,
                net_income=metric.net_income if metric else None,
            )
        )
        filter_results["filter"] = filter_decision
        if not filter_decision.passed:
            await self._record_decision(company.ticker, "filter", filter_decision)
            return SelectionResult(
                ticker=company.ticker,
                passed_selection=False,
                filter_results=filter_results,
                disqualification_reason=filter_decision.reason,
            )

        # 2. BUSINESS MODEL AGENT — Clarity check
        business_decision = await self.business_model_agent.evaluate(
            ticker=company.ticker,
            company_name=company.name,
            description=company.description,
            segments=None,  # TODO: Load from database
        )
        filter_results["business_model"] = business_decision
        if not business_decision.passed:
            await self._record_decision(company.ticker, "business_model", business_decision)
            return SelectionResult(
                ticker=company.ticker,
                passed_selection=False,
                filter_results=filter_results,
                disqualification_reason=business_decision.reason,
            )

        # 3. FOUNDER AGENT — Alignment check
        founder_decision = await self.founder_agent.evaluate(
            founder_ownership=founder_ownership,
            insider_ownership=insider_ownership,
            founder_name=company.founder_name,
            recent_insider_buys=recent_insider_buys,
        )
        filter_results["founder"] = founder_decision
        if not founder_decision.passed:
            await self._record_decision(company.ticker, "founder", founder_decision)
            return SelectionResult(
                ticker=company.ticker,
                passed_selection=False,
                filter_results=filter_results,
                disqualification_reason=founder_decision.reason,
            )

        # 4. GROWTH AGENT — Growth quality
        growth_decision = await self.growth_agent.evaluate(
            organic_revenue_growth=organic_revenue_growth,
            total_revenue_growth=metric.revenue_growth_3yr_cagr if metric else None,
            major_acquisitions_3yr=major_acquisitions_3yr,
            acquisition_spend=acquisition_spend,
            fcf=metric.fcf if metric else None,
        )
        filter_results["growth"] = growth_decision
        if not growth_decision.passed:
            await self._record_decision(company.ticker, "growth", growth_decision)
            return SelectionResult(
                ticker=company.ticker,
                passed_selection=False,
                filter_results=filter_results,
                disqualification_reason=growth_decision.reason,
            )

        # 5. RED FLAG AGENT — Catch learned red flags
        # Calculate derived metrics
        buyback_to_fcf_ratio = None
        if metric and metric.stock_repurchased and metric.fcf and metric.fcf > 0:
            buyback_to_fcf_ratio = float(metric.stock_repurchased / metric.fcf)

        stock_dilution_rate = None
        if metric and metric.stock_based_compensation and metric.revenue and metric.revenue > 0:
            stock_dilution_rate = float(metric.stock_based_compensation / metric.revenue)

        red_flag_decision = await self.red_flag_agent.evaluate(
            ticker=company.ticker,
            buyback_to_fcf_ratio=buyback_to_fcf_ratio,
            stock_dilution_rate=stock_dilution_rate,
            apic_growth_vs_re_growth=None,  # TODO: Calculate from historical balance sheet
            fcf=metric.fcf if metric else None,
            capex=metric.capex if metric else None,
            net_debt_ebitda=metric.net_debt_ebitda if metric else None,
        )
        filter_results["red_flag"] = red_flag_decision
        if not red_flag_decision.passed:
            await self._record_decision(company.ticker, "red_flag", red_flag_decision)
            return SelectionResult(
                ticker=company.ticker,
                passed_selection=False,
                filter_results=filter_results,
                disqualification_reason=red_flag_decision.reason,
            )

        # All agents passed!
        await self._record_decision(company.ticker, "all", None)
        return SelectionResult(
            ticker=company.ticker,
            passed_selection=True,
            filter_results=filter_results,
            disqualification_reason=None,
        )

    async def _record_decision(
        self, ticker: str, agent_type: str, decision
    ) -> None:
        """Record agent decision to database for learning."""
        try:
            decision_obj = SelectionAgentDecision(
                company_ticker=ticker,
                agent_type=agent_type,
                passed_filter=decision.passed if decision else True,
                score=decision.score if decision else None,
                reason=decision.reason if decision else "Passed all agents",
                decision_data=decision.metadata if decision else {},
            )
            self.session.add(decision_obj)
            await self.session.flush()
        except Exception as e:
            logger.warning(f"Failed to record selection decision for {ticker}: {e}")

    async def apply_learned_filters(
        self, company: Company, metric: Metric | None
    ) -> tuple[bool, str | None]:
        """
        Check if company matches any learned filter patterns.
        Returns (should_filter_out, reason).
        """
        try:
            from src.db.models.learned_patterns import SelectionLearnedPattern

            stmt = _select(SelectionLearnedPattern).where(
                SelectionLearnedPattern.agent_type.in_(["filter", "red_flag"]),
                SelectionLearnedPattern.expires_at > datetime.utcnow(),
                SelectionLearnedPattern.confidence > 0.75,
            )
            result = await self.session.execute(stmt)
            patterns = result.scalars().all()

            for pattern in patterns:
                if (
                    pattern.metric_name == "buyback_to_fcf_ratio"
                    and metric
                    and hasattr(metric, "buyback_to_fcf_ratio")
                    and metric.buyback_to_fcf_ratio
                ):
                    threshold = pattern.new_threshold.get("threshold", 1.0)
                    if metric.buyback_to_fcf_ratio > threshold:
                        return (
                            True,
                            f"Learned filter: {pattern.pattern_type} "
                            f"({pattern.confidence:.0%} confidence)",
                        )

            return False, None
        except Exception as e:
            logger.warning(f"Error applying learned filters: {e}")
            return False, None

    async def _load_company_metrics(self, ticker: str) -> Metric | None:
        """Load latest metrics for company from the shared session."""
        try:
            return await self.metric_repo.get_latest(ticker)
        except Exception as e:
            logger.debug(f"Failed to load metrics for {ticker}: {e}")
            return None

    async def _load_alignment_data(self, ticker: str) -> tuple[float | None, float | None, int]:
        """Load founder and insider ownership data."""
        founder_ownership = None
        insider_ownership = None
        recent_insider_buys = 0

        try:
            # Use session.get() — Company PK is ticker
            company = await self.session.get(Company, ticker)
            if company and company.is_founder_led:
                # Assume meaningful stake when flagged as founder-led but no exact % stored
                founder_ownership = 0.05

            # Check for recent insider purchases (last 90 days — wider window than 30d for data coverage)
            try:
                stmt = _select(_func.count(InsiderPurchase.id)).where(
                    InsiderPurchase.ticker == ticker,
                    InsiderPurchase.transaction_date >= datetime.utcnow() - timedelta(days=90),
                )
                result = await self.session.execute(stmt)
                recent_insider_buys = result.scalar() or 0
            except Exception as e:
                logger.debug(f"Failed to query insider purchases for {ticker}: {e}")

            # Try to get insider ownership from metrics
            metric = await self._load_company_metrics(ticker)
            if metric and hasattr(metric, "insider_ownership_pct") and metric.insider_ownership_pct:
                insider_ownership = float(metric.insider_ownership_pct)

        except Exception as e:
            logger.warning(f"Failed to load alignment data for {ticker}: {e}")

        return founder_ownership, insider_ownership, recent_insider_buys

    async def _load_acquisition_data(self, ticker: str) -> tuple[int, float]:
        """Load acquisition history."""
        metric = await self._load_company_metrics(ticker)

        major_acquisitions_3yr = 0
        acquisition_spend = 0.0

        if metric and metric.acquisitions_net:
            acquisition_spend = float(metric.acquisitions_net)
            # Flag as major if spending > $100M
            if acquisition_spend > 100_000_000:
                major_acquisitions_3yr = 1

        return major_acquisitions_3yr, acquisition_spend

    async def _calculate_organic_growth(self, ticker: str) -> float | None:
        """Calculate organic revenue growth (approximation)."""
        metric = await self._load_company_metrics(ticker)

        if not metric:
            return None

        # Use 3-year CAGR as approximation of organic growth
        # In practice, would subtract acquisition contribution
        if metric.revenue_growth_3yr_cagr:
            return float(metric.revenue_growth_3yr_cagr)

        return None
