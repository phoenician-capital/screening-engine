"""
Quick-start script: run the full scoring pipeline manually.

Usage:  python scripts/run_pipeline.py [--tickers AAPL,MSFT] [--type weekly]
"""

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from src.shared.logging import setup_logging


async def main(tickers: list[str] | None, run_type: str):
    setup_logging()

    from src.db.session import async_session_factory
    from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
    from src.orchestration.pipelines.memo_pipeline import MemoPipeline

    async with async_session_factory() as session:
        # Run scoring
        pipeline = ScoringPipeline(session)
        results = await pipeline.run(tickers=tickers, run_type=run_type)
        print(f"\nScored {len(results)} companies:")
        for r in results[:20]:
            print(f"  #{r['rank']:>3} {r['ticker']:<8} Fit={r['fit_score']:.0f}  Risk={r['risk_score']:.0f}")

        # Generate memos for top 10
        memo_pipeline = MemoPipeline(session)
        memos = await memo_pipeline.generate_top_memos(top_n=10)
        print(f"\nGenerated {len(memos)} memos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers")
    parser.add_argument("--type", type=str, default="manual", choices=["manual", "daily", "weekly"])
    args = parser.parse_args()

    ticker_list = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    asyncio.run(main(ticker_list, args.type))
