"""
Scheduled jobs — daily and weekly routines.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_factory
from src.orchestration.discovery.universe_expander import UniverseExpander
from src.orchestration.pipelines.memo_pipeline import MemoPipeline
from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline

logger = logging.getLogger(__name__)


class DailyJob:
    """
    Daily job: insider conviction refresh, 8-K scan, IR monitor, email digest.
    """

    async def run(self) -> dict:
        logger.info("Starting daily job")
        results = {}

        async with async_session_factory() as session:
            # 1. Refresh insider conviction clusters
            from src.ingestion.workers.insider_conviction_worker import InsiderConvictionWorker
            conviction_result = await InsiderConvictionWorker().run_for_universe(session)
            results["insider_clusters"] = conviction_result.get("clusters_detected", 0)

            # 2. Scan for new 8-K filings (last 24h)
            from src.ingestion.workers.eightk_scanner import EightKScanner
            eightk_signals = await EightKScanner().scan_universe(session, lookback_hours=24)
            results["8k_signals"] = len(eightk_signals)
            await session.commit()

            # 3. Re-score tickers flagged by 8-K scanner
            pipeline = ScoringPipeline(session)
            rescore_tickers = list({s["ticker"] for s in eightk_signals if s.get("trigger_rescore")})
            if rescore_tickers:
                logger.info("Re-scoring %d tickers from 8-K triggers", len(rescore_tickers))
                await pipeline.run(tickers=rescore_tickers, run_type="8k_triggered")

            # 4. Daily scoring run (all companies)
            scored = await pipeline.run(run_type="daily")
            results["scored"] = len(scored)

            # 5. Generate memos for top 5
            memo_pipeline = MemoPipeline(session)
            memos = await memo_pipeline.generate_top_memos(top_n=5)
            results["memos_generated"] = len(memos)

            # 6. IR monitor — check all portfolio company IR pages
            from src.ingestion.workers.ir_monitor_worker import IRMonitorWorker
            new_ir_events = await IRMonitorWorker().run(session)
            await session.commit()
            results["new_ir_events"] = len(new_ir_events)

            # 7. Compose and send digest if anything notable
            high_signal_8ks = [s for s in eightk_signals if s.get("relevance_score", 0) >= 0.7]
            if new_ir_events or high_signal_8ks:
                from src.ingestion.workers.digest_composer import DigestComposer
                from src.shared.email.smtp_sender import send_digest_email
                subject, body = DigestComposer().compose_daily_digest(
                    ir_events=new_ir_events,
                    high_signal_8ks=high_signal_8ks,
                    cluster_buys=[],
                )
                sent = await send_digest_email(subject=subject, body_html=body)
                results["digest_sent"] = sent

        logger.info("Daily job complete: %s", results)
        return results


class WeeklyJob:
    """
    Weekly job (Monday): full universe refresh, transcript analysis,
    portfolio similarity expansion, full re-rank.
    """

    async def run(self) -> dict:
        logger.info("Starting weekly job")
        results = {}

        async with async_session_factory() as session:
            # 1. Portfolio similarity expansion
            from src.orchestration.discovery.portfolio_similarity import PortfolioSimilarityExpander
            similarity_results = await PortfolioSimilarityExpander(session).run(max_analogs_per_holding=5)
            results["portfolio_analogs"] = sum(len(v) for v in similarity_results.values())

            # 2. Expand universe
            expander = UniverseExpander(session)
            new_screener = await expander.expand_via_screener()
            results["new_from_screener"] = len(new_screener)

            new_thematic = await expander.expand_via_thematic()
            results["new_from_themes"] = len(new_thematic)

            # 3. Ingest new tickers
            all_new = list(dict.fromkeys(new_screener + new_thematic))
            if all_new:
                ingested = await expander.ingest_new_tickers(all_new[:50])
                results["newly_ingested"] = ingested

            # 4. Transcript analysis for all active companies
            from src.ingestion.workers.transcript_analyzer import TranscriptAnalyzer
            from src.db.repositories.company_repo import CompanyRepository
            companies = await CompanyRepository(session).get_active()
            transcript_count = 0
            analyzer = TranscriptAnalyzer()
            for company in companies[:30]:  # Cap at 30 to limit API costs
                try:
                    result = await analyzer.analyze_company(company.ticker, session, num_quarters=3)
                    if result.get("signals"):
                        transcript_count += 1
                except Exception as e:
                    logger.debug("Transcript analysis failed for %s: %s", company.ticker, e)
            await session.commit()
            results["transcripts_analyzed"] = transcript_count

            # 5. Full scoring run
            pipeline = ScoringPipeline(session)
            scored = await pipeline.run(run_type="weekly")
            results["total_scored"] = len(scored)

            # 6. Generate memos for top 20
            memo_pipeline = MemoPipeline(session)
            memos = await memo_pipeline.generate_top_memos(top_n=20)
            results["memos_generated"] = len(memos)

        logger.info("Weekly job complete: %s", results)
        return results
