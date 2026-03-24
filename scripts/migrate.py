"""
Run all database migrations in order.
Called on container startup before the main app.
Uses psycopg2 (sync) to avoid asyncio executor issues during startup.
"""
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


def run_migrations():
    db_user     = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host     = os.getenv("DB_HOST")
    db_port     = os.getenv("DB_PORT", "5432")
    db_name     = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_host, db_name]):
        logger.info("DB env vars not set — skipping migrations")
        return

    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not installed — skipping migrations")
        return

    ssl_mode = "require" if os.getenv("DB_SSL") else "prefer"
    try:
        conn = psycopg2.connect(
            host=db_host, port=int(db_port), dbname=db_name,
            user=db_user, password=db_password, sslmode=ssl_mode,
            connect_timeout=10,
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Enable extensions
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        logger.info("Extensions ready")

        # Migration tracking table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Apply all .sql files in order
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for f in sql_files:
            cur.execute("SELECT 1 FROM _migrations WHERE filename = %s", (f.name,))
            if cur.fetchone():
                logger.info("  skip %s (already applied)", f.name)
                continue
            try:
                cur.execute(f.read_text())
                cur.execute("INSERT INTO _migrations (filename) VALUES (%s)", (f.name,))
                logger.info("  applied %s", f.name)
            except Exception as e:
                logger.warning("  %s failed (may already exist): %s", f.name, e)

        cur.close()
        conn.close()
        logger.info("Migrations complete")

    except Exception as e:
        logger.warning("Migration failed (skipping): %s", e)


if __name__ == "__main__":
    run_migrations()
