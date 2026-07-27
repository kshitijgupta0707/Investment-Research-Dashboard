"""Query history read-back.

The write side is covered in `test_research`, which records every run including
the failures. What matters here is the boundary: history is the analyst's own
record, so a colleague's queries must not appear in it even though the two share
an organization and a workspace of reports.
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
from app.models import research_queries as queries_model
from app.routes import queries as query_routes
from app.schemas.auth import CurrentUser
from app.services import queries as service

ORG_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000000")


def a_user(name: str, org: uuid.UUID = ORG_A) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
        auth_id=uuid.uuid5(uuid.NAMESPACE_URL, name),
        email=f"{name}@test.invalid",
        org_id=org,
        role="analyst",
    )


A1 = a_user("a1")


def a_row(
    query_text: str = "What is the latest news on Tesla?",
    tools: list[str] | None = None,
    status: str = "success",
    latency_ms: int | None = 1200,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "query_text": query_text,
        "tools_selected": tools if tools is not None else ["get_news_sentiment"],
        "status": status,
        "latency_ms": latency_ms,
        "created_at": datetime.now(UTC),
    }


class FakePool:
    def __init__(self, *, rows: list[dict[str, Any]] | None = None, total: int = 0) -> None:
        self.rows = rows or []
        self.total = total

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self.rows

    async def fetchval(self, sql: str, *args: Any) -> int:
        return self.total


# --- reading ----------------------------------------------------------------


async def test_history_reports_the_total_before_pagination() -> None:
    pool = FakePool(rows=[a_row(), a_row()], total=9)

    page = await service.list_history(pool, A1, limit=2, offset=4)

    assert (len(page.items), page.total, page.limit, page.offset) == (2, 9, 2, 4)


@pytest.mark.parametrize(("limit", "expected"), [(0, 1), (500, service.MAX_PAGE_SIZE), (20, 20)])
async def test_page_size_is_clamped(limit: int, expected: int) -> None:
    page = await service.list_history(FakePool(), A1, limit=limit)

    assert page.limit == expected


async def test_a_negative_offset_is_clamped() -> None:
    page = await service.list_history(FakePool(), A1, offset=-5)

    assert page.offset == 0


async def test_history_carries_the_tools_the_agent_chose() -> None:
    """The evidence that tool choice varies per query, kept where a reader sees it."""
    pool = FakePool(
        rows=[
            a_row("Latest news on Tesla?", ["get_news_sentiment"]),
            a_row("What is a P/E ratio?", []),
        ],
        total=2,
    )

    page = await service.list_history(pool, A1)

    assert [e.tools_selected for e in page.items] == [["get_news_sentiment"], []]


@pytest.mark.parametrize("status", ["success", "partial", "failed"])
async def test_every_recorded_status_reads_back(status: str) -> None:
    """Failed runs belong in history -- they are exactly what a user re-runs."""
    pool = FakePool(rows=[a_row(status=status)], total=1)

    page = await service.list_history(pool, A1)

    assert page.items[0].status == status


async def test_a_missing_latency_is_allowed() -> None:
    """`latency_ms` is nullable; a run that died before timing has none."""
    pool = FakePool(rows=[a_row(latency_ms=None)], total=1)

    page = await service.list_history(pool, A1)

    assert page.items[0].latency_ms is None


async def test_an_empty_history_is_a_page_not_an_error() -> None:
    page = await service.list_history(FakePool(), A1)

    assert (page.items, page.total) == ([], 0)


# --- the endpoint -----------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    pool = FakePool(rows=[a_row()], total=1)
    monkeypatch.setattr(query_routes.db, "get_pool", lambda: pool)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(query_routes.router)
    app.dependency_overrides[get_current_user] = lambda: A1

    return TestClient(app, raise_server_exceptions=False)


def test_the_endpoint_returns_a_page(client) -> None:
    body = client.get("/api/queries").json()

    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["tools_selected"] == ["get_news_sentiment"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
def test_out_of_range_pagination_is_400(client, query: str) -> None:
    """Clamped in the service, but rejected at the edge so the contract is explicit."""
    assert client.get(f"/api/queries?{query}").status_code == 400


def test_the_endpoint_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(query_routes.db, "get_pool", lambda: FakePool())

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(query_routes.router)

    assert TestClient(app).get("/api/queries").status_code == 401


# --- against the real database ----------------------------------------------


class TxPool:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def fetch(self, sql: str, *args: Any) -> Any:
        return await self._conn.fetch(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return await self._conn.fetchval(sql, *args)

    async def execute(self, sql: str, *args: Any) -> Any:
        return await self._conn.execute(sql, *args)


class Seeded:
    def __init__(self, pool: TxPool, org_a: uuid.UUID, a1: uuid.UUID, a2: uuid.UUID) -> None:
        self.pool = pool
        self.org_a = org_a
        self.a1 = a1
        self.a2 = a2

    async def ran(
        self,
        query_text: str,
        *,
        user: uuid.UUID | None = None,
        tools: list[str] | None = None,
        status: str = "success",
    ) -> uuid.UUID:
        return await queries_model.record(
            self.pool,
            org_id=self.org_a,
            user_id=user or self.a1,
            query_text=query_text,
            tools_selected=tools or [],
            status=status,  # type: ignore[arg-type]
            latency_ms=1000,
        )


@pytest.fixture
async def live(settings, requires_db):
    conn = await asyncpg.connect(settings.database_url, timeout=20)
    tx = conn.transaction()
    await tx.start()
    try:
        org_a = await conn.fetchval("insert into organizations (name) values ('A') returning id")

        async def a_member(email: str) -> uuid.UUID:
            return await conn.fetchval(
                """insert into users (supabase_auth_id, email, org_id, role)
                   values (gen_random_uuid(), $1, $2, 'analyst') returning id""",
                email,
                org_a,
            )

        yield Seeded(TxPool(conn), org_a, await a_member("a1@live.invalid"), await a_member("a2@live.invalid"))
    finally:
        await tx.rollback()
        await conn.close()


async def test_live_history_round_trips(live) -> None:
    """Chiefly: does the `text[]` column survive as a list?"""
    await live.ran("Latest news on Tesla?", tools=["get_news_sentiment"], status="partial")

    rows, total = await queries_model.list_for_user(live.pool, live.org_a, live.a1)

    assert total == 1
    assert rows[0]["tools_selected"] == ["get_news_sentiment"]
    assert rows[0]["status"] == "partial"


async def test_live_a_colleagues_queries_are_not_mine(live) -> None:
    """Reports are shared across the org; history is not."""
    await live.ran("mine", user=live.a1)
    await live.ran("theirs", user=live.a2)

    rows, total = await queries_model.list_for_user(live.pool, live.org_a, live.a1)

    assert total == 1
    assert rows[0]["query_text"] == "mine"


async def test_live_history_is_newest_first(live) -> None:
    """Timestamps are set explicitly, because `now()` is transaction-fixed.

    Every insert here shares one transaction, so all three rows would otherwise
    carry an identical `created_at` and the ordering assertion would be decided
    by the random-uuid tiebreaker.
    """
    for day, text in enumerate(("first", "second", "third"), start=1):
        query_id = await live.ran(text)
        await live.pool.execute(
            "update research_queries set created_at = $2 where id = $1",
            query_id,
            datetime(2026, 7, day, tzinfo=UTC),
        )

    rows, _ = await queries_model.list_for_user(live.pool, live.org_a, live.a1)

    assert [r["query_text"] for r in rows] == ["third", "second", "first"]


async def test_live_pagination_reports_the_full_total(live) -> None:
    for i in range(5):
        await live.ran(f"query {i}")

    rows, total = await queries_model.list_for_user(live.pool, live.org_a, live.a1, limit=2, offset=1)

    assert (len(rows), total) == (2, 5)


async def test_live_a_zero_tool_query_is_still_history(live) -> None:
    """"What is a P/E ratio?" selects nothing and is still worth recording."""
    await live.ran("What is a P/E ratio?", tools=[])

    rows, total = await queries_model.list_for_user(live.pool, live.org_a, live.a1)

    assert total == 1
    assert rows[0]["tools_selected"] == []
