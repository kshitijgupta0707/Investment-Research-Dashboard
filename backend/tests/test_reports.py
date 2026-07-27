"""Saved report CRUD.

Two layers, because they fail in different ways:

* **Permissions and shapes** run against a fake pool -- fast, and they cover the
  rules that matter most: org-wide read, creator-or-admin write, and 404 rather
  than 403 for another tenant's id.
* **The SQL itself** runs against the real database inside a rolled-back
  transaction. Tag filtering, full-text search, ordering and the `updated_at`
  trigger are all database behaviour that a fake pool would happily fake wrong.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import _register_codecs
from app.middleware.auth import get_current_user
from app.middleware.errors import register_exception_handlers
from app.models import reports as reports_model
from app.routes import reports as reports_routes
from app.schemas.auth import CurrentUser
from app.schemas.reports import ReportCreate
from app.services import reports as service

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
B1 = a_user("b1", org=ORG_B)

REPORT_JSON: dict[str, Any] = {
    "summary": "NVIDIA is performing strongly.",
    "sections": [
        {
            "title": "Overview",
            "type": "text",
            "content": {"text": "Revenue grew."},
            "confidence": "high",
            "sources": [{"type": "api", "label": "yfinance", "url": None, "data_as_of": None}],
        }
    ],
    "partial": False,
    "failed_tools": [],
    "generated_at": "2026-07-27T10:00:00Z",
}


def a_row(
    *,
    created_by: uuid.UUID = A1.id,
    tags: list[str] | None = None,
    report_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": report_id or uuid.uuid4(),
        "query_text": "How is NVIDIA doing?",
        "tags": tags if tags is not None else ["risk"],
        "created_by": created_by,
        "created_by_email": "a1@test.invalid",
        "created_at": now,
        "updated_at": now,
        "structured_result": REPORT_JSON,
    }


class FakePool:
    """Returns a canned row and records what was written."""

    def __init__(
        self,
        *,
        row: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
        total: int = 0,
        deleted: bool = True,
    ) -> None:
        self.row = row
        self.rows = rows or []
        self.total = total
        self.deleted = deleted
        self.audit: list[tuple[Any, ...]] = []
        self.queries: list[str] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.queries.append(sql)
        return self.row

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(sql)
        return self.rows

    async def fetchval(self, sql: str, *args: Any) -> int:
        self.queries.append(sql)
        return self.total

    async def execute(self, sql: str, *args: Any) -> str:
        self.queries.append(sql)
        if "audit_logs" in sql:
            self.audit.append(args)
            return "INSERT 0 1"
        return "DELETE 1" if self.deleted else "DELETE 0"

    @property
    def audit_actions(self) -> list[str]:
        return [entry[2] for entry in self.audit]


def a_payload(tags: list[str] | None = None) -> ReportCreate:
    return ReportCreate(
        query_text="How is NVIDIA doing?",
        structured_result=REPORT_JSON,  # type: ignore[arg-type]
        tags=tags or [],
    )


# --- creating ---------------------------------------------------------------


async def test_saving_returns_the_stored_report() -> None:
    pool = FakePool(row=a_row(tags=["risk"]))

    report = await service.create_report(pool, A1, a_payload(["risk"]))

    assert report.query_text == "How is NVIDIA doing?"
    assert report.tags == ["risk"]
    assert report.structured_result.summary == "NVIDIA is performing strongly."


async def test_saving_is_audited() -> None:
    pool = FakePool(row=a_row())

    await service.create_report(pool, A1, a_payload(["risk"]))

    assert pool.audit_actions == [service.ACTION_CREATED]


async def test_a_malformed_result_is_rejected_at_write_time() -> None:
    """Anything stored is handed straight back to the renderer later."""
    with pytest.raises(ValueError):
        ReportCreate(
            query_text="How is NVIDIA doing?",
            structured_result={"summary": "no sections key is fine, but this is not a report"},  # type: ignore[arg-type]
            tags=[],
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (["Risk", "RISK", " risk "], ["risk"]),
        (["Earnings", "risk"], ["earnings", "risk"]),
        ([" ", ""], []),
    ],
)
def test_tags_are_normalised(raw: list[str], expected: list[str]) -> None:
    assert a_payload(raw).tags == expected


@pytest.mark.parametrize(
    "tags",
    [["x" * 33], [f"tag{i}" for i in range(11)]],
)
def test_unreasonable_tags_are_rejected(tags: list[str]) -> None:
    with pytest.raises(ValueError):
        a_payload(tags)


# --- reading ----------------------------------------------------------------


async def test_reading_a_missing_report_is_404() -> None:
    pool = FakePool(row=None)

    with pytest.raises(Exception) as exc:
        await service.get_report(pool, A1, uuid.uuid4())
    assert getattr(exc.value, "status_code", None) == 404


async def test_a_colleague_can_read_the_report( ) -> None:
    """The workspace is shared: org-wide read is the intended behaviour."""
    pool = FakePool(row=a_row(created_by=A1.id))

    report = await service.get_report(pool, A2, uuid.uuid4())

    assert report.created_by == A1.id


async def test_the_list_page_reports_the_total() -> None:
    pool = FakePool(rows=[a_row(), a_row()], total=7)

    page = await service.list_reports(pool, A1, limit=2, offset=4)

    assert (len(page.items), page.total, page.limit, page.offset) == (2, 7, 2, 4)


async def test_the_list_omits_the_structured_result() -> None:
    pool = FakePool(rows=[a_row()], total=1)

    page = await service.list_reports(pool, A1)

    assert not hasattr(page.items[0], "structured_result")


@pytest.mark.parametrize(("limit", "expected"), [(0, 1), (500, service.MAX_PAGE_SIZE), (20, 20)])
async def test_page_size_is_clamped(limit: int, expected: int) -> None:
    pool = FakePool(rows=[], total=0)

    page = await service.list_reports(pool, A1, limit=limit)

    assert page.limit == expected


# --- ownership --------------------------------------------------------------


@pytest.mark.parametrize("user", [A1, A_ADMIN], ids=["creator", "admin"])
async def test_permitted_users_can_edit_tags(user: CurrentUser) -> None:
    pool = FakePool(row=a_row(created_by=A1.id, tags=["updated"]))

    report = await service.update_report_tags(pool, user, uuid.uuid4(), ["updated"])

    assert report.tags == ["updated"]
    assert service.ACTION_UPDATED in pool.audit_actions


async def test_an_analyst_cannot_edit_a_colleagues_report() -> None:
    pool = FakePool(row=a_row(created_by=A1.id))

    with pytest.raises(Exception) as exc:
        await service.update_report_tags(pool, A2, uuid.uuid4(), ["nope"])

    assert getattr(exc.value, "status_code", None) == 403
    assert pool.audit == []


@pytest.mark.parametrize("user", [A1, A_ADMIN], ids=["creator", "admin"])
async def test_permitted_users_can_delete(user: CurrentUser) -> None:
    pool = FakePool(row=a_row(created_by=A1.id))

    await service.delete_report(pool, user, uuid.uuid4())

    assert service.ACTION_DELETED in pool.audit_actions


async def test_an_analyst_cannot_delete_a_colleagues_report() -> None:
    pool = FakePool(row=a_row(created_by=A1.id))

    with pytest.raises(Exception) as exc:
        await service.delete_report(pool, A2, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 403
    assert pool.audit == []


@pytest.mark.parametrize("action", ["update", "delete"])
async def test_another_orgs_report_is_404_not_403(action: str) -> None:
    """403 would confirm the id exists, which is enough to enumerate ids."""
    # The org filter is in the WHERE clause, so a foreign id simply finds nothing.
    pool = FakePool(row=None)

    with pytest.raises(Exception) as exc:
        if action == "update":
            await service.update_report_tags(pool, B1, uuid.uuid4(), ["x"])
        else:
            await service.delete_report(pool, B1, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 404


async def test_an_admin_of_another_org_has_no_power_here() -> None:
    """Admin is scoped to an organization, not global."""
    foreign_admin = a_user("b_admin", org=ORG_B, role="admin")
    pool = FakePool(row=None)

    with pytest.raises(Exception) as exc:
        await service.delete_report(pool, foreign_admin, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 404


# --- the endpoints ----------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    pool = FakePool(row=a_row(created_by=A1.id), rows=[a_row()], total=1)
    monkeypatch.setattr(reports_routes.db, "get_pool", lambda: pool)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(reports_routes.router)
    app.dependency_overrides[get_current_user] = lambda: A1

    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.pool = pool  # type: ignore[attr-defined]
    return test_client


def test_create_returns_201_and_the_envelope(client) -> None:
    response = client.post(
        "/api/reports",
        json={"query_text": "How is NVIDIA doing?", "structured_result": REPORT_JSON, "tags": ["risk"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["structured_result"]["summary"] == "NVIDIA is performing strongly."


def test_list_returns_a_page(client) -> None:
    body = client.get("/api/reports").json()

    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert "structured_result" not in body["data"]["items"][0]


def test_get_returns_the_full_report(client) -> None:
    body = client.get(f"/api/reports/{uuid.uuid4()}").json()

    assert set(body["data"]["structured_result"]) == {
        "summary",
        "sections",
        "partial",
        "failed_tools",
        "generated_at",
    }


def test_patch_updates_tags(client) -> None:
    response = client.patch(f"/api/reports/{uuid.uuid4()}", json={"tags": ["Risk", "risk"]})

    assert response.status_code == 200


def test_delete_returns_the_envelope_not_a_bare_204(client) -> None:
    response = client.delete(f"/api/reports/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_a_missing_report_is_404_through_the_endpoint(client) -> None:
    client.pool.row = None

    response = client.get(f"/api/reports/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_a_malformed_id_is_400(client) -> None:
    response = client.get("/api/reports/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "payload",
    [
        {"query_text": "", "structured_result": REPORT_JSON},
        {"query_text": "  ", "structured_result": REPORT_JSON},
        {"query_text": "How is NVIDIA doing?"},
        {"query_text": "How is NVIDIA doing?", "structured_result": {"nope": True}},
    ],
)
def test_invalid_create_payloads_are_400(client, payload: dict[str, Any]) -> None:
    response = client.post("/api/reports", json=payload)

    assert response.status_code == 400


def test_the_endpoints_require_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports_routes.db, "get_pool", lambda: FakePool())

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(reports_routes.router)

    assert TestClient(app).get("/api/reports").status_code == 401


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
    def __init__(self, pool: TxPool, org_a: uuid.UUID, org_b: uuid.UUID, a1: uuid.UUID, b1: uuid.UUID) -> None:
        self.pool = pool
        self.org_a = org_a
        self.org_b = org_b
        self.a1 = a1
        self.b1 = b1

    async def save(self, query_text: str, tags: list[str] | None = None) -> Any:
        return await reports_model.create(
            self.pool,
            org_id=self.org_a,
            created_by=self.a1,
            query_text=query_text,
            structured_result=REPORT_JSON,
            tags=tags or [],
        )


@pytest.fixture
async def live(settings, requires_db):
    conn = await asyncpg.connect(settings.database_url, timeout=20)
    await _register_codecs(conn)
    tx = conn.transaction()
    await tx.start()
    try:
        org_a = await conn.fetchval("insert into organizations (name) values ('A') returning id")
        org_b = await conn.fetchval("insert into organizations (name) values ('B') returning id")
        a1 = await conn.fetchval(
            """insert into users (supabase_auth_id, email, org_id, role)
               values (gen_random_uuid(), 'a1@live.invalid', $1, 'analyst') returning id""",
            org_a,
        )
        b1 = await conn.fetchval(
            """insert into users (supabase_auth_id, email, org_id, role)
               values (gen_random_uuid(), 'b1@live.invalid', $1, 'analyst') returning id""",
            org_b,
        )
        yield Seeded(TxPool(conn), org_a, org_b, a1, b1)
    finally:
        await tx.rollback()
        await conn.close()


async def test_live_a_saved_report_round_trips(live) -> None:
    """Chiefly: does `structured_result` survive jsonb intact?"""
    created = await live.save("How is NVIDIA doing?", ["risk"])

    row = await reports_model.get(live.pool, live.org_a, created["id"])

    assert row is not None
    assert row["structured_result"] == REPORT_JSON
    assert row["tags"] == ["risk"]
    assert row["created_by_email"] == "a1@live.invalid"


async def test_live_another_org_cannot_read_it(live) -> None:
    created = await live.save("How is NVIDIA doing?")

    assert await reports_model.get(live.pool, live.org_b, created["id"]) is None


async def test_live_the_tag_filter_is_exact_and_indexed(live) -> None:
    await live.save("Tagged risk", ["risk"])
    await live.save("Tagged earnings", ["earnings"])

    rows, total = await reports_model.list_for_org(live.pool, live.org_a, tag="risk")

    assert total == 1
    assert rows[0]["query_text"] == "Tagged risk"


async def test_live_the_tag_filter_is_case_insensitive(live) -> None:
    await live.save("Tagged", ["risk"])

    _, total = await reports_model.list_for_org(live.pool, live.org_a, tag="RISK")

    assert total == 1


async def test_live_search_matches_word_variants(live) -> None:
    """Full-text, not substring: 'compare' finds 'comparing'.

    Note it does *not* find "comparison" -- Postgres's English stemmer reduces
    `compare` to `compar` but leaves `comparison` alone. Real stemming, not
    magic.
    """
    await live.save("Comparing chipmakers in detail")
    await live.save("Latest news on Tesla")

    rows, total = await reports_model.list_for_org(live.pool, live.org_a, search="compare")

    assert total == 1
    assert rows[0]["query_text"] == "Comparing chipmakers in detail"


async def test_live_search_and_tag_combine(live) -> None:
    await live.save("NVIDIA risk review", ["risk"])
    await live.save("NVIDIA earnings review", ["earnings"])

    _, total = await reports_model.list_for_org(live.pool, live.org_a, tag="risk", search="NVIDIA")

    assert total == 1


async def test_live_reports_are_newest_first(live) -> None:
    """Timestamps are set explicitly, because `now()` is transaction-fixed.

    Every insert in this fixture shares one transaction, so all three rows would
    otherwise carry an identical `created_at` and the ordering assertion would
    be decided by the random-uuid tiebreaker.
    """
    for day, text in enumerate(("first", "second", "third"), start=1):
        created = await live.save(text)
        await live.pool.execute(
            "update research_reports set created_at = $2 where id = $1",
            created["id"],
            datetime(2026, 7, day, tzinfo=UTC),
        )

    rows, _ = await reports_model.list_for_org(live.pool, live.org_a)

    assert [r["query_text"] for r in rows] == ["third", "second", "first"]


async def test_live_pagination_reports_the_full_total(live) -> None:
    for i in range(5):
        await live.save(f"report {i}")

    rows, total = await reports_model.list_for_org(live.pool, live.org_a, limit=2, offset=1)

    assert (len(rows), total) == (2, 5)


async def test_live_updating_tags_bumps_updated_at(live) -> None:
    """`updated_at` is a database trigger, not application code."""
    created = await live.save("How is NVIDIA doing?", ["risk"])
    await live.pool.execute(
        "update research_reports set updated_at = '2000-01-01' where id = $1", created["id"]
    )

    updated = await reports_model.update_tags(live.pool, live.org_a, created["id"], ["earnings"])

    assert updated is not None
    assert updated["tags"] == ["earnings"]
    assert updated["updated_at"].year > 2000


async def test_live_delete_removes_only_the_targeted_row(live) -> None:
    keep = await live.save("keep me")
    drop = await live.save("drop me")

    assert await reports_model.delete(live.pool, live.org_a, drop["id"]) is True
    assert await reports_model.get(live.pool, live.org_a, drop["id"]) is None
    assert await reports_model.get(live.pool, live.org_a, keep["id"]) is not None


async def test_live_delete_across_orgs_removes_nothing(live) -> None:
    created = await live.save("mine")

    assert await reports_model.delete(live.pool, live.org_b, created["id"]) is False
    assert await reports_model.get(live.pool, live.org_a, created["id"]) is not None
