"""Watchlist add / list / remove.

The rule under test throughout is that a watchlist is **per user**, not per org.
Reports are deliberately shared across an organization; these are not, and the
tests that matter most are the ones showing a colleague in the same org is as
locked out as someone in a different one.

Two layers, as in `test_reports`: permissions and shapes against a fake pool,
and the SQL itself against the real database inside a rolled-back transaction --
the unique constraint and the idempotent re-add are database behaviour a fake
pool would happily fake wrong.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user
from app.middleware.errors import register_exception_handlers
from app.models import watchlist as watchlist_model
from app.routes import watchlist as watchlist_routes
from app.schemas.auth import CurrentUser
from app.schemas.watchlist import WatchlistAdd
from app.services import watchlist as service

# --- shared fixtures --------------------------------------------------------

ORG_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000000")
ORG_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000000")


def a_user(name: str, org: uuid.UUID = ORG_A, role: str = "analyst") -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
        auth_id=uuid.uuid5(uuid.NAMESPACE_URL, name),
        email=f"{name}@test.invalid",
        org_id=org,
        role=role,  # type: ignore[arg-type]
    )


A1 = a_user("a1")
A2 = a_user("a2")
A_ADMIN = a_user("a_admin", role="admin")


def an_entry(ticker: str = "NVDA", company_name: str | None = "NVIDIA Corporation") -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "ticker": ticker,
        "company_name": company_name,
        "created_at": datetime.now(UTC),
    }


class FakePool:
    """Canned rows, plus a record of what was written."""

    def __init__(
        self,
        *,
        inserted: dict[str, Any] | None = None,
        existing: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
        deleted: bool = True,
    ) -> None:
        self.inserted = inserted
        self.existing = existing
        self.rows = rows or []
        self.deleted = deleted
        self.audit: list[tuple[Any, ...]] = []
        self.queries: list[str] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.queries.append(sql)
        # The model inserts first and only falls back to a select on conflict.
        if "insert into watchlist" in sql:
            return self.inserted
        return self.existing

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(sql)
        return self.rows

    async def execute(self, sql: str, *args: Any) -> str:
        self.queries.append(sql)
        if "audit_logs" in sql:
            self.audit.append(args)
            return "INSERT 0 1"
        return "DELETE 1" if self.deleted else "DELETE 0"

    @property
    def audit_actions(self) -> list[str]:
        return [entry[2] for entry in self.audit]


# --- adding -----------------------------------------------------------------


async def test_adding_returns_the_pinned_entry() -> None:
    pool = FakePool(inserted=an_entry())

    entry, created = await service.add_entry(pool, A1, WatchlistAdd(ticker="NVDA"))

    assert created is True
    assert entry.ticker == "NVDA"
    assert entry.company_name == "NVIDIA Corporation"


async def test_adding_is_audited() -> None:
    pool = FakePool(inserted=an_entry())

    await service.add_entry(pool, A1, WatchlistAdd(ticker="NVDA"))

    assert pool.audit_actions == [service.ACTION_ADDED]


async def test_re_adding_returns_the_existing_entry() -> None:
    """Pressing the button twice is not an error."""
    already_there = an_entry()
    pool = FakePool(inserted=None, existing=already_there)

    entry, created = await service.add_entry(pool, A1, WatchlistAdd(ticker="NVDA"))

    assert created is False
    assert entry.id == already_there["id"]


async def test_a_no_op_add_is_not_audited() -> None:
    """Nothing changed, so an audit line would only obscure the real ones."""
    pool = FakePool(inserted=None, existing=an_entry())

    await service.add_entry(pool, A1, WatchlistAdd(ticker="NVDA"))

    assert pool.audit == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("nvda", "NVDA"), (" nvda ", "NVDA"), ("BRK.B", "BRK.B"), ("ry.to", "RY.TO")],
)
def test_tickers_are_normalised(raw: str, expected: str) -> None:
    """Upper-casing on the way in is what makes the unique constraint mean something."""
    assert WatchlistAdd(ticker=raw).ticker == expected


@pytest.mark.parametrize("ticker", ["", "   ", "N" * 13, "NV DA", "nvda!", "$NVDA", "-NVDA"])
def test_unreasonable_tickers_are_rejected(ticker: str) -> None:
    with pytest.raises(ValueError):
        WatchlistAdd(ticker=ticker)


@pytest.mark.parametrize(("raw", "expected"), [("  ", None), (None, None), (" NVIDIA ", "NVIDIA")])
def test_company_name_is_optional_and_trimmed(raw: str | None, expected: str | None) -> None:
    assert WatchlistAdd(ticker="NVDA", company_name=raw).company_name == expected


def test_an_overlong_company_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        WatchlistAdd(ticker="NVDA", company_name="x" * 121)


# --- reading ----------------------------------------------------------------


async def test_listing_returns_the_users_entries() -> None:
    pool = FakePool(rows=[an_entry("AMD", None), an_entry("NVDA")])

    entries = await service.list_entries(pool, A1)

    assert [e.ticker for e in entries] == ["AMD", "NVDA"]
    assert entries[0].company_name is None


async def test_an_empty_watchlist_is_a_list_not_an_error() -> None:
    entries = await service.list_entries(FakePool(rows=[]), A1)

    assert entries == []


# --- removing ---------------------------------------------------------------


async def test_removing_is_audited() -> None:
    pool = FakePool(deleted=True)

    await service.remove_entry(pool, A1, uuid.uuid4())

    assert pool.audit_actions == [service.ACTION_REMOVED]


async def test_removing_something_absent_is_404() -> None:
    pool = FakePool(deleted=False)

    with pytest.raises(Exception) as exc:
        await service.remove_entry(pool, A1, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 404
    assert pool.audit == []


@pytest.mark.parametrize("user", [A2, A_ADMIN], ids=["colleague", "admin"])
async def test_a_colleagues_entry_is_404_not_403(user: CurrentUser) -> None:
    """A watchlist is personal, so even an admin has no route to another's.

    There is no ownership branch to test here: `user_id` is in the WHERE clause,
    so the row is simply not found. Admin is included to show the report rules
    were not copied across -- an admin may delete a colleague's *report*, but
    not their watchlist.
    """
    pool = FakePool(deleted=False)

    with pytest.raises(Exception) as exc:
        await service.remove_entry(pool, user, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 404


# --- the endpoints ----------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    pool = FakePool(inserted=an_entry(), rows=[an_entry()])
    monkeypatch.setattr(watchlist_routes.db, "get_pool", lambda: pool)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(watchlist_routes.router)
    app.dependency_overrides[get_current_user] = lambda: A1

    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.pool = pool  # type: ignore[attr-defined]
    return test_client


def test_a_new_pin_is_201(client) -> None:
    response = client.post("/api/watchlist", json={"ticker": "nvda"})

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["ticker"] == "NVDA"


def test_re_pinning_is_200_not_409(client) -> None:
    client.pool.inserted = None
    client.pool.existing = an_entry()

    response = client.post("/api/watchlist", json={"ticker": "NVDA"})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_list_returns_the_entries(client) -> None:
    body = client.get("/api/watchlist").json()

    assert body["success"] is True
    assert body["data"][0]["ticker"] == "NVDA"


def test_delete_returns_the_envelope_not_a_bare_204(client) -> None:
    response = client.delete(f"/api/watchlist/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_deleting_something_absent_is_404(client) -> None:
    client.pool.deleted = False

    response = client.delete(f"/api/watchlist/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_a_malformed_id_is_400(client) -> None:
    response = client.delete("/api/watchlist/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "payload",
    [{}, {"ticker": ""}, {"ticker": "   "}, {"ticker": "N" * 13}, {"ticker": "NV DA"}],
)
def test_invalid_payloads_are_400(client, payload: dict[str, Any]) -> None:
    assert client.post("/api/watchlist", json=payload).status_code == 400


def test_the_endpoints_require_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchlist_routes.db, "get_pool", lambda: FakePool())

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(watchlist_routes.router)

    assert TestClient(app).get("/api/watchlist").status_code == 401


# --- against the real database ----------------------------------------------


class TxPool:
    """Pool-shaped, but every call runs in one transaction that is rolled back."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        return await self._conn.fetchrow(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> Any:
        return await self._conn.fetch(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return await self._conn.fetchval(sql, *args)

    async def execute(self, sql: str, *args: Any) -> Any:
        return await self._conn.execute(sql, *args)


class Seeded:
    def __init__(
        self,
        pool: TxPool,
        org_a: uuid.UUID,
        org_b: uuid.UUID,
        a1: uuid.UUID,
        a2: uuid.UUID,
        b1: uuid.UUID,
    ) -> None:
        self.pool = pool
        self.org_a = org_a
        self.org_b = org_b
        self.a1 = a1
        self.a2 = a2
        self.b1 = b1

    async def pin(self, ticker: str, *, user: uuid.UUID | None = None, name: str | None = None) -> Any:
        row, _ = await watchlist_model.add(
            self.pool,
            org_id=self.org_a if user in (None, self.a1, self.a2) else self.org_b,
            user_id=user or self.a1,
            ticker=ticker,
            company_name=name,
        )
        return row


@pytest.fixture
async def live(settings, requires_db):
    conn = await asyncpg.connect(settings.database_url, timeout=20)
    tx = conn.transaction()
    await tx.start()
    try:
        org_a = await conn.fetchval("insert into organizations (name) values ('A') returning id")
        org_b = await conn.fetchval("insert into organizations (name) values ('B') returning id")

        async def a_member(email: str, org: uuid.UUID) -> uuid.UUID:
            return await conn.fetchval(
                """insert into users (supabase_auth_id, email, org_id, role)
                   values (gen_random_uuid(), $1, $2, 'analyst') returning id""",
                email,
                org,
            )

        a1 = await a_member("a1@live.invalid", org_a)
        a2 = await a_member("a2@live.invalid", org_a)
        b1 = await a_member("b1@live.invalid", org_b)
        yield Seeded(TxPool(conn), org_a, org_b, a1, a2, b1)
    finally:
        await tx.rollback()
        await conn.close()


async def test_live_a_pin_round_trips(live) -> None:
    created = await live.pin("NVDA", name="NVIDIA Corporation")

    rows = await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)

    assert [r["id"] for r in rows] == [created["id"]]
    assert rows[0]["company_name"] == "NVIDIA Corporation"


async def test_live_re_pinning_is_idempotent(live) -> None:
    """The unique constraint is real; `on conflict do nothing` is what absorbs it."""
    first = await live.pin("NVDA")

    row, created = await watchlist_model.add(
        live.pool, org_id=live.org_a, user_id=live.a1, ticker="NVDA", company_name=None
    )

    assert created is False
    assert row["id"] == first["id"]
    assert len(await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)) == 1


async def test_live_the_same_ticker_is_separate_per_user(live) -> None:
    """The constraint is on (org, user, ticker) -- two analysts may both track NVDA."""
    await live.pin("NVDA", user=live.a1)
    await live.pin("NVDA", user=live.a2)

    assert len(await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)) == 1
    assert len(await watchlist_model.list_for_user(live.pool, live.org_a, live.a2)) == 1


async def test_live_a_colleague_does_not_see_it(live) -> None:
    await live.pin("NVDA", user=live.a1)

    assert await watchlist_model.list_for_user(live.pool, live.org_a, live.a2) == []


async def test_live_another_org_does_not_see_it(live) -> None:
    await live.pin("NVDA", user=live.a1)

    assert await watchlist_model.list_for_user(live.pool, live.org_b, live.b1) == []


async def test_live_entries_are_alphabetical(live) -> None:
    for ticker in ("NVDA", "AMD", "INTC"):
        await live.pin(ticker)

    rows = await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)

    assert [r["ticker"] for r in rows] == ["AMD", "INTC", "NVDA"]


async def test_live_delete_removes_only_the_targeted_row(live) -> None:
    keep = await live.pin("AMD")
    drop = await live.pin("NVDA")

    assert await watchlist_model.delete(live.pool, live.org_a, live.a1, drop["id"]) is True

    rows = await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)
    assert [r["id"] for r in rows] == [keep["id"]]


async def test_live_delete_across_users_removes_nothing(live) -> None:
    created = await live.pin("NVDA", user=live.a1)

    assert await watchlist_model.delete(live.pool, live.org_a, live.a2, created["id"]) is False
    assert len(await watchlist_model.list_for_user(live.pool, live.org_a, live.a1)) == 1
