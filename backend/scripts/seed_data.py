"""Seed two demo organizations with users, reports, history and watchlists.

Usage:
    python backend/scripts/seed_data.py             # full seed, incl. Supabase auth users
    python backend/scripts/seed_data.py --db-only   # database rows only, no login
    python backend/scripts/seed_data.py --dry-run   # report what would be written

Re-running is safe. The demo organizations are deleted and rebuilt, which
cascades to their users, reports, history, watchlists, invites and audit rows --
so the seed is a reset, not an accumulation.

By default the script also provisions the demo users in Supabase Auth, because
the demo workflows the brief asks for are all "log in as X and then as Y". That
needs `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Without them, use `--db-only`:
the data lands and the API can be exercised with a token you supply yourself,
but the seeded accounts cannot sign in.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2
from psycopg2.extensions import connection as Connection

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.demo_data import DEMO_PASSWORD, DemoOrg, DemoUser, demo_orgs  # noqa: E402
from app.services.org import generate_code  # noqa: E402
from app.utils.config import Settings, get_settings  # noqa: E402

# Supabase pages its admin user list; a demo project never has many.
_PAGE_SIZE = 200
_MAX_PAGES = 10
_HTTP_TIMEOUT = 30


# --- Supabase Auth ----------------------------------------------------------


def _admin_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
    }


def _find_auth_user(base: str, headers: dict[str, str], email: str) -> str | None:
    """Look up an existing auth user by address, paging the admin list."""
    target = email.lower()
    for page in range(1, _MAX_PAGES + 1):
        response = httpx.get(
            f"{base}/auth/v1/admin/users",
            headers=headers,
            params={"page": page, "per_page": _PAGE_SIZE},
            timeout=_HTTP_TIMEOUT,
        )
        response.raise_for_status()
        users = response.json().get("users", [])
        for user in users:
            if (user.get("email") or "").lower() == target:
                return user["id"]
        if len(users) < _PAGE_SIZE:
            return None
    return None


def provision_auth_user(settings: Settings, email: str, password: str) -> str:
    """Create the auth user, or reset an existing one's password.

    Idempotent on purpose: re-seeding must leave the documented credentials
    working, and an address left over from a previous run is the normal case
    rather than an error.
    """
    base = settings.supabase_url.rstrip("/")
    headers = _admin_headers(settings)

    created = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=_HTTP_TIMEOUT,
    )
    if created.status_code in (200, 201):
        return created.json()["id"]

    existing = _find_auth_user(base, headers, email)
    if existing is None:
        raise RuntimeError(f"could not create or find {email}: {created.status_code} {created.text}")

    updated = httpx.put(
        f"{base}/auth/v1/admin/users/{existing}",
        headers=headers,
        json={"password": password, "email_confirm": True},
        timeout=_HTTP_TIMEOUT,
    )
    updated.raise_for_status()
    return existing


def resolve_auth_ids(
    settings: Settings, orgs: list[DemoOrg], password: str, *, db_only: bool
) -> dict[str, str]:
    """Map each demo user key to the auth id its `users` row will carry."""
    if db_only:
        # A random id keeps the not-null unique column satisfied. Nothing can
        # sign in as these accounts, which is what --db-only means.
        return {user.key: str(uuid.uuid4()) for org in orgs for user in org.users}

    auth_ids: dict[str, str] = {}
    for org in orgs:
        for user in org.users:
            print(f"  auth  {user.email:<28} ", end="", flush=True)
            auth_ids[user.key] = provision_auth_user(settings, user.email, password)
            print("ok")
    return auth_ids


# --- database ---------------------------------------------------------------


def wipe(conn: Connection, names: list[str]) -> int:
    """Remove the demo organizations. Cascades to everything they own."""
    with conn.cursor() as cur:
        cur.execute("delete from organizations where name = any(%s)", (names,))
        return cur.rowcount


def seed_org(conn: Connection, org: DemoOrg, auth_ids: dict[str, str], now: datetime) -> str:
    """Insert one organization and everything in it. Returns its invite code."""
    with conn.cursor() as cur:
        cur.execute("insert into organizations (name) values (%s) returning id", (org.name,))
        org_id = cur.fetchone()[0]

        user_ids: dict[str, str] = {}
        for user in org.users:
            cur.execute(
                """
                insert into users (supabase_auth_id, email, name, org_id, role)
                values (%s, %s, %s, %s, %s) returning id
                """,
                (auth_ids[user.key], user.email, user.name, org_id, user.role),
            )
            user_ids[user.key] = cur.fetchone()[0]

        code = generate_code()
        cur.execute(
            """
            insert into org_invites (org_id, created_by, code, expires_at)
            values (%s, %s, %s, %s)
            """,
            (org_id, user_ids[org.admin.key], code, now + timedelta(days=30)),
        )

        for saved in org.reports:
            created_at = now - timedelta(days=saved.age_days)
            cur.execute(
                """
                insert into research_reports
                    (org_id, created_by, query_text, structured_result, tags, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    org_id,
                    user_ids[saved.author],
                    saved.query_text,
                    json.dumps(saved.report.model_dump(mode="json")),
                    saved.tags,
                    created_at,
                    created_at,
                ),
            )

        for ran in org.queries:
            cur.execute(
                """
                insert into research_queries
                    (org_id, user_id, query_text, tools_selected, status, latency_ms, created_at)
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    org_id,
                    user_ids[ran.author],
                    ran.query_text,
                    ran.tools_selected,
                    ran.status,
                    ran.latency_ms,
                    now - timedelta(hours=ran.age_hours),
                ),
            )

        for pin in org.watchlist:
            cur.execute(
                """
                insert into watchlist (org_id, user_id, ticker, company_name)
                values (%s, %s, %s, %s)
                """,
                (org_id, user_ids[pin.owner], pin.ticker, pin.company_name),
            )

    return code


# --- reporting --------------------------------------------------------------


def describe(orgs: list[DemoOrg]) -> None:
    for org in orgs:
        print(f"\n  {org.name}")
        for user in org.users:
            print(f"    {user.role:<8} {user.email}")
        print(
            f"    {len(org.reports)} report(s), {len(org.queries)} history row(s), "
            f"{len(org.watchlist)} watchlist entr(ies)"
        )


def print_credentials(orgs: list[DemoOrg], codes: dict[str, str], password: str) -> None:
    print("\nSign in with any of these:\n")
    for org in orgs:
        print(f"  {org.name}   (invite code: {codes[org.name]})")
        for user in org.users:
            print(f"    {user.role:<8} {user.email:<28} {password}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written")
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="skip Supabase Auth; seeded accounts will not be able to sign in",
    )
    parser.add_argument("--password", default=DEMO_PASSWORD, help="password for the demo accounts")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    orgs = demo_orgs(now)

    if args.dry_run:
        print("Would seed:")
        describe(orgs)
        return 0

    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    db_only = args.db_only
    if not db_only and not (settings.supabase_url and settings.supabase_secret_key):
        print("SUPABASE_URL / SUPABASE_SECRET_KEY are not set. Re-run with --db-only to")
        print("seed the database anyway -- the demo accounts will not be able to sign in.")
        return 1

    try:
        auth_ids = resolve_auth_ids(settings, orgs, args.password, db_only=db_only)
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"\nSupabase Auth provisioning failed: {exc}")
        return 1

    codes: dict[str, str] = {}
    with psycopg2.connect(settings.database_url) as conn:
        try:
            removed = wipe(conn, [org.name for org in orgs])
            for org in orgs:
                codes[org.name] = seed_org(conn, org, auth_ids, now)
            conn.commit()
        except psycopg2.Error as exc:
            conn.rollback()
            print(f"\nSeeding failed and was rolled back. Nothing was written.\n{exc}")
            return 1

    print(f"\nReplaced {removed} existing demo organization(s).")
    describe(orgs)

    if db_only:
        print("\n--db-only: no Supabase accounts were created, so these users cannot sign in.")
    else:
        print_credentials(orgs, codes, args.password)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
