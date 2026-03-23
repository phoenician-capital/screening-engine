"""
Run all database migrations in order.
Called on container startup before the main app.
"""
import asyncio
import logging
import os
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def run_migrations():
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_host, db_name]):
        logger.info("DB env vars not set — skipping migrations")
        return

    ssl = os.getenv("DB_SSL", "")
    dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    if ssl:
        dsn += f"?ssl={ssl}"

    conn = await asyncpg.connect(dsn)
    try:
        # Enable pgvector
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("pgvector extension ready")

        # Track applied migrations
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Apply all .sql files in order
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for f in sql_files:
            already = await conn.fetchval(
                "SELECT 1 FROM _migrations WHERE filename = $1", f.name
            )
            if already:
                continue
            sql = f.read_text()
            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (filename) VALUES ($1)", f.name
                )
                logger.info("Applied migration: %s", f.name)
            except Exception as e:
                logger.warning("Migration %s failed (may already exist): %s", f.name, e)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
