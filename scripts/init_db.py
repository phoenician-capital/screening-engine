"""
Initialize the database by running the SQL migration.

Usage:  python scripts/init_db.py
"""

import sys

sys.path.insert(0, ".")

from src.config.settings import settings


def main():
    import psycopg2

    print(f"Connecting to {settings.db.host}:{settings.db.port}/{settings.db.name}...")
    conn = psycopg2.connect(settings.db.sync_dsn)
    conn.autocommit = True
    cur = conn.cursor()

    migration_path = settings.project_root / "src" / "db" / "migrations" / "001_initial_schema.sql"
    print(f"Running migration: {migration_path}")

    with open(migration_path, "r") as f:
        sql = f.read()

    cur.execute(sql)
    print("Migration complete.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
