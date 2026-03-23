"""
Quick-start script: ingest one or more tickers.

Usage:  python scripts/ingest_tickers.py AAPL MSFT GOOG
"""

import asyncio
import sys

sys.path.insert(0, ".")

from src.shared.logging import setup_logging


async def main(tickers: list[str]):
    setup_logging()

    from src.db.session import async_session_factory
    from src.ingestion.workers.ingestion_worker import IngestionWorker

    async with async_session_factory() as session:
        worker = IngestionWorker(session)
        results = await worker.ingest_batch(tickers)
        await session.commit()

        for r in results:
            print(f"\n{r['ticker']}:")
            for step, status in r["steps"].items():
                print(f"  {step}: {status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_tickers.py TICKER1 TICKER2 ...")
        sys.exit(1)

    tickers = [t.upper() for t in sys.argv[1:]]
    asyncio.run(main(tickers))
