"""Apply pending SQL migrations to the configured Postgres database.

Usage:
    python backend/scripts/migrate.py            # apply everything pending
    python backend/scripts/migrate.py --status   # report without changing anything
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Connection

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.config import get_settings  # noqa: E402

MIGRATIONS_DIR = BACKEND_ROOT / "migrations"

# RLS with no policy denies everyone. The migration runner connects with a
# privileged role that bypasses it, but this keeps the table off PostgREST.
TRACKING_TABLE_DDL = """
create table if not exists schema_migrations (
    filename    text primary key,
    checksum    text not null,
    applied_at  timestamptz not null default now()
);
alter table schema_migrations enable row level security;
"""


def discover_migrations() -> list[Path]:
    """Return migration files in lexical order, which is their apply order."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def fetch_applied(conn: Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(TRACKING_TABLE_DDL)
        cur.execute("select filename, checksum from schema_migrations")
        return dict(cur.fetchall())


def apply_migration(conn: Connection, path: Path) -> None:
    """Run one migration and record it. The whole file commits or none of it does."""
    with conn.cursor() as cur:
        cur.execute(path.read_text(encoding="utf-8"))
        cur.execute(
            "insert into schema_migrations (filename, checksum) values (%s, %s)",
            (path.name, checksum(path)),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="show which migrations are applied or pending, then exit",
    )
    args = parser.parse_args()

    database_url = get_settings().database_url
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    migrations = discover_migrations()
    if not migrations:
        print(f"No migrations found in {MIGRATIONS_DIR}")
        return 0

    with psycopg2.connect(database_url) as conn:
        applied = fetch_applied(conn)
        conn.commit()

        if args.status:
            for path in migrations:
                if path.name not in applied:
                    state = "pending"
                elif applied[path.name] != checksum(path):
                    state = "APPLIED, but the file changed since"
                else:
                    state = "applied"
                print(f"  {path.name:<40} {state}")
            return 0

        pending = [p for p in migrations if p.name not in applied]
        if not pending:
            print(f"Up to date -- {len(applied)} migration(s) already applied.")
            return 0

        for path in pending:
            print(f"Applying {path.name} ...", end=" ", flush=True)
            try:
                apply_migration(conn, path)
                conn.commit()
            except psycopg2.Error as exc:
                conn.rollback()
                print("failed")
                print(f"\n{path.name} rolled back. Nothing was partially applied.\n{exc}")
                return 1
            print("ok")

        print(f"Applied {len(pending)} migration(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
