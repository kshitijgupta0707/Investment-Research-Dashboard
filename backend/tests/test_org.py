"""Organization management: provisioning, members, invite codes.

Three things are worth testing here and the rest is plumbing:

* **Provisioning works without a membership.** A caller founding an organization
  or redeeming a code has no tenant yet, so these are the only endpoints that
  depend on the bare identity rather than on `get_current_user`.
* **Admin gating is server-side.** An analyst calling an admin endpoint directly
  gets 403 -- the demo the brief asks for, not a hidden button.
* **Redemption is atomic and does not leak.** Wrong, revoked and lapsed codes
  are one indistinguishable answer, and validity is decided in the same
  statement that inserts the membership.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import get_authenticated_identity, get_current_user
from app.middleware.errors import register_exception_handlers
from app.models import org_invites as invites_model
from app.models import organizations as orgs_model
from app.routes import org as org_routes
from app.schemas.auth import AuthenticatedIdentity, CurrentUser
from app.schemas.org import OrgCreate, OrgJoin
from app.services import org as service

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


A_ADMIN = a_user("a_admin", role="admin")
A1 = a_user("a1")

NEWCOMER = AuthenticatedIdentity(auth_id=uuid.uuid4(), email="new@test.invalid")
ANONYMOUS = AuthenticatedIdentity(auth_id=uuid.uuid4(), email=None)


def a_membership(role: str = "admin") -> dict[str, Any]:
    return {
        "user_id": uuid.uuid4(),
        "org_id": ORG_A,
        "org_name": "Northwind Capital",
        "role": role,
    }


def an_invite(
    *,
    status: str = "active",
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "code": "7KQP4M2XRT",
        "status": status,
        "expires_at": expires_at if expires_at is not None else datetime.now(UTC) + timedelta(days=7),
        "created_at": datetime.now(UTC),
        "created_by_email": "a_admin@test.invalid",
    }


def a_member_row(email: str = "a1@test.invalid", role: str = "analyst") -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "email": email,
        "name": None,
        "role": role,
        "created_at": datetime.now(UTC),
    }


class FakePool:
    """Dispatches on the statement, because this service touches four tables."""

    def __init__(
        self,
        *,
        created: dict[str, Any] | None = None,
        joined: dict[str, Any] | None = None,
        org: dict[str, Any] | None = None,
        invite: dict[str, Any] | None = None,
        revoked: dict[str, Any] | None = None,
        members: list[dict[str, Any]] | None = None,
        invites: list[dict[str, Any]] | None = None,
        conflict: bool = False,
    ) -> None:
        self.created = created
        self.joined = joined
        self.org = org
        self.invite = invite
        self.revoked = revoked
        self.members = members or []
        self.invites = invites or []
        self.conflict = conflict
        self.audit: list[tuple[Any, ...]] = []
        self.codes: list[str] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        if "insert into organizations" in sql:
            if self.conflict:
                raise asyncpg.UniqueViolationError("users_supabase_auth_id_key")
            return self.created
        if "with invite as" in sql:
            if self.conflict:
                raise asyncpg.UniqueViolationError("users_supabase_auth_id_key")
            return self.joined
        if "insert into org_invites" in sql:
            self.codes.append(args[2])
            if self.conflict:
                raise asyncpg.UniqueViolationError("org_invites_code_key")
            return self.invite
        if "update org_invites" in sql:
            return self.revoked
        return self.org

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self.invites if "org_invites" in sql else self.members

    async def execute(self, sql: str, *args: Any) -> str:
        if "audit_logs" in sql:
            self.audit.append(args)
        return "INSERT 0 1"

    @property
    def audit_actions(self) -> list[str]:
        return [entry[2] for entry in self.audit]

    @property
    def audit_metadata(self) -> list[Any]:
        return [entry[5] for entry in self.audit]


# --- founding an organization -----------------------------------------------


async def test_founding_makes_you_an_admin() -> None:
    pool = FakePool(created=a_membership("admin"))

    membership = await service.create_org(pool, NEWCOMER, OrgCreate(name="Northwind Capital"))

    assert membership.role == "admin"
    assert membership.org_name == "Northwind Capital"


async def test_founding_is_audited() -> None:
    pool = FakePool(created=a_membership())

    await service.create_org(pool, NEWCOMER, OrgCreate(name="Northwind Capital"))

    assert pool.audit_actions == [service.ACTION_ORG_CREATED]


async def test_signing_up_twice_is_409() -> None:
    """The unique constraint on supabase_auth_id is the guard, not a pre-check."""
    pool = FakePool(conflict=True)

    with pytest.raises(Exception) as exc:
        await service.create_org(pool, NEWCOMER, OrgCreate(name="Second Org"))

    assert getattr(exc.value, "status_code", None) == 409


async def test_a_token_without_an_email_cannot_provision() -> None:
    """`users.email` is not nullable, so there is nothing to insert."""
    with pytest.raises(Exception) as exc:
        await service.create_org(FakePool(), ANONYMOUS, OrgCreate(name="Northwind"))

    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.parametrize("name", ["", " ", "x", "y" * 121])
def test_unreasonable_org_names_are_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        OrgCreate(name=name)


# --- joining with a code ----------------------------------------------------


async def test_joining_makes_you_an_analyst() -> None:
    """Founders are admins; joiners are not. That is the whole role split."""
    pool = FakePool(joined=a_membership("analyst"))

    membership = await service.join_org(pool, NEWCOMER, OrgJoin(code="7KQP4M2XRT"))

    assert membership.role == "analyst"


async def test_joining_is_audited() -> None:
    pool = FakePool(joined=a_membership("analyst"))

    await service.join_org(pool, NEWCOMER, OrgJoin(code="7KQP4M2XRT"))

    assert pool.audit_actions == [service.ACTION_MEMBER_JOINED]


async def test_an_unusable_code_is_404() -> None:
    """Wrong, revoked and lapsed are one answer -- the statement returns no row."""
    pool = FakePool(joined=None)

    with pytest.raises(Exception) as exc:
        await service.join_org(pool, NEWCOMER, OrgJoin(code="BADCODE123"))

    assert getattr(exc.value, "status_code", None) == 404
    assert pool.audit == []


async def test_joining_when_already_a_member_is_409() -> None:
    pool = FakePool(conflict=True)

    with pytest.raises(Exception) as exc:
        await service.join_org(pool, NEWCOMER, OrgJoin(code="7KQP4M2XRT"))

    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.parametrize(
    "raw",
    ["7KQP4M2XRT", "7kqp4m2xrt", " 7KQP-4M2X-RT ", "7kqp 4m2x rt", "7KQP-4M2X-RT\n"],
)
def test_codes_are_normalised_the_way_people_paste_them(raw: str) -> None:
    assert OrgJoin(code=raw).code == "7KQP4M2XRT"


@pytest.mark.parametrize("code", ["", "   ", "----", "  - "])
def test_a_code_of_nothing_is_rejected(code: str) -> None:
    with pytest.raises(ValueError):
        OrgJoin(code=code)


# --- invite codes -----------------------------------------------------------


def test_generated_codes_avoid_ambiguous_characters() -> None:
    """Codes get read aloud; I/L/O/U/0/1 are where that goes wrong."""
    codes = "".join(service.generate_code() for _ in range(200))

    assert len(service.generate_code()) == service.CODE_LENGTH
    assert not set(codes) & set("ILOU01")
    assert set(codes) <= set(service._ALPHABET)


def test_generated_codes_are_not_repeated() -> None:
    assert len({service.generate_code() for _ in range(500)}) == 500


async def test_an_invite_expires_by_default() -> None:
    pool = FakePool(invite=an_invite())

    invite = await service.create_invite(pool, A_ADMIN)

    assert invite.expires_at is not None
    assert invite.expired is False


async def test_the_audit_entry_does_not_carry_the_code() -> None:
    """The audit log is org-readable; a live code in it is a standing way in."""
    pool = FakePool(invite=an_invite())

    await service.create_invite(pool, A_ADMIN)

    assert pool.audit_actions == [service.ACTION_INVITE_CREATED]
    assert "7KQP4M2XRT" not in str(pool.audit_metadata)


async def test_a_lapsed_invite_reads_back_as_expired() -> None:
    """Nothing sweeps the table, so 'active' and lapsed is a real state."""
    pool = FakePool(invites=[an_invite(expires_at=datetime.now(UTC) - timedelta(days=1))])

    invites = await service.list_invites(pool, A_ADMIN)

    assert invites[0].status == "active"
    assert invites[0].expired is True


async def test_a_never_expiring_invite_is_not_expired() -> None:
    pool = FakePool(invites=[an_invite(expires_at=None)])

    assert (await service.list_invites(pool, A_ADMIN))[0].expired is False


async def test_revoking_is_audited() -> None:
    pool = FakePool(revoked=an_invite(status="revoked"))

    invite = await service.revoke_invite(pool, A_ADMIN, uuid.uuid4())

    assert invite.status == "revoked"
    assert pool.audit_actions == [service.ACTION_INVITE_REVOKED]


async def test_revoking_something_absent_is_404() -> None:
    pool = FakePool(revoked=None)

    with pytest.raises(Exception) as exc:
        await service.revoke_invite(pool, A_ADMIN, uuid.uuid4())

    assert getattr(exc.value, "status_code", None) == 404
    assert pool.audit == []


# --- the endpoints ----------------------------------------------------------


def an_app(pool: FakePool, *, user: CurrentUser | None = None) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(org_routes.router)
    app.dependency_overrides[get_authenticated_identity] = lambda: NEWCOMER
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def pool(monkeypatch: pytest.MonkeyPatch) -> FakePool:
    fake = FakePool(
        created=a_membership("admin"),
        joined=a_membership("analyst"),
        org={"id": ORG_A, "name": "Northwind Capital", "member_count": 3, "created_at": datetime.now(UTC)},
        invite=an_invite(),
        revoked=an_invite(status="revoked"),
        members=[a_member_row("a_admin@test.invalid", "admin"), a_member_row()],
        invites=[an_invite()],
    )
    monkeypatch.setattr(org_routes.db, "get_pool", lambda: fake)
    return fake


def test_founding_is_201(pool: FakePool) -> None:
    response = an_app(pool).post("/api/org", json={"name": "Northwind Capital"})

    assert response.status_code == 201
    assert response.json()["data"]["role"] == "admin"


def test_joining_is_201(pool: FakePool) -> None:
    response = an_app(pool).post("/api/org/join", json={"code": "7kqp-4m2x-rt"})

    assert response.status_code == 201
    assert response.json()["data"]["role"] == "analyst"


def test_provisioning_needs_no_membership(pool: FakePool) -> None:
    """`get_current_user` is deliberately not overridden here.

    If these endpoints depended on it, this call would 401 -- a new user could
    never reach the only endpoints that could give them a membership.
    """
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(org_routes.router)
    app.dependency_overrides[get_authenticated_identity] = lambda: NEWCOMER

    response = TestClient(app).post("/api/org", json={"name": "Northwind Capital"})

    assert response.status_code == 201


def test_any_member_may_read_their_own_org(pool: FakePool) -> None:
    body = an_app(pool, user=A1).get("/api/org").json()

    assert body["data"]["name"] == "Northwind Capital"
    assert body["data"]["member_count"] == 3


def test_an_admin_sees_the_member_list(pool: FakePool) -> None:
    body = an_app(pool, user=A_ADMIN).get("/api/org/members").json()

    assert [m["role"] for m in body["data"]] == ["admin", "analyst"]


def test_an_admin_can_mint_and_revoke(pool: FakePool) -> None:
    client = an_app(pool, user=A_ADMIN)

    assert client.post("/api/org/invites").status_code == 201
    assert client.get("/api/org/invites").status_code == 200
    assert client.delete(f"/api/org/invites/{uuid.uuid4()}").status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/org/members"),
        ("post", "/api/org/invites"),
        ("get", "/api/org/invites"),
        ("delete", f"/api/org/invites/{uuid.uuid4()}"),
    ],
)
def test_an_analyst_is_403_on_every_admin_endpoint(pool: FakePool, method: str, path: str) -> None:
    """The demo the brief asks for: enforced server-side, not by hiding buttons."""
    response = getattr(an_app(pool, user=A1), method)(path)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_the_member_endpoints_require_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(org_routes.db, "get_pool", lambda: FakePool())

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(org_routes.router)

    assert TestClient(app).get("/api/org").status_code == 401
    assert TestClient(app).get("/api/org/members").status_code == 401
    assert TestClient(app).post("/api/org", json={"name": "Northwind"}).status_code == 401


def test_a_malformed_invite_id_is_400(pool: FakePool) -> None:
    response = an_app(pool, user=A_ADMIN).delete("/api/org/invites/not-a-uuid")

    assert response.status_code == 400


# --- against the real database ----------------------------------------------


class TxPool:
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
    def __init__(self, pool: TxPool, org_a: uuid.UUID, org_b: uuid.UUID, admin: uuid.UUID) -> None:
        self.pool = pool
        self.org_a = org_a
        self.org_b = org_b
        self.admin = admin

    async def invite(
        self, code: str, *, expires_at: datetime | None = None, org: uuid.UUID | None = None
    ) -> Any:
        return await invites_model.create(
            self.pool,
            org_id=org or self.org_a,
            created_by=self.admin,
            code=code,
            expires_at=expires_at if expires_at is not None else datetime.now(UTC) + timedelta(days=7),
        )


@pytest.fixture
async def live(settings, requires_db):
    conn = await asyncpg.connect(settings.database_url, timeout=20)
    tx = conn.transaction()
    await tx.start()
    try:
        org_a = await conn.fetchval("insert into organizations (name) values ('A') returning id")
        org_b = await conn.fetchval("insert into organizations (name) values ('B') returning id")
        admin = await conn.fetchval(
            """insert into users (supabase_auth_id, email, org_id, role)
               values (gen_random_uuid(), 'admin@live.invalid', $1, 'admin') returning id""",
            org_a,
        )
        yield Seeded(TxPool(conn), org_a, org_b, admin)
    finally:
        await tx.rollback()
        await conn.close()


async def test_live_founding_creates_both_rows_atomically(live) -> None:
    row = await orgs_model.create_with_admin(
        live.pool,
        name="Northwind Capital",
        auth_id=uuid.uuid4(),
        email="founder@live.invalid",
        user_name="Founder",
    )

    assert row["org_name"] == "Northwind Capital"
    assert row["role"] == "admin"

    org = await orgs_model.get(live.pool, row["org_id"])
    assert org["member_count"] == 1


async def test_live_a_second_signup_violates_the_unique_constraint(live) -> None:
    """What the 409 is built on. Two orgs from one identity must be impossible."""
    auth_id = uuid.uuid4()
    await orgs_model.create_with_admin(
        live.pool, name="First", auth_id=auth_id, email="f@live.invalid", user_name=None
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await orgs_model.create_with_admin(
            live.pool, name="Second", auth_id=auth_id, email="f@live.invalid", user_name=None
        )


async def test_live_a_valid_code_joins_as_an_analyst(live) -> None:
    await live.invite("LIVECODE01")

    row = await orgs_model.join_with_code(
        live.pool, code="LIVECODE01", auth_id=uuid.uuid4(), email="joiner@live.invalid", user_name=None
    )

    assert row is not None
    assert row["org_id"] == live.org_a
    assert row["role"] == "analyst"


@pytest.mark.parametrize("code", ["NOSUCHCODE", "livecode01"])
async def test_live_a_wrong_code_creates_nobody(live, code: str) -> None:
    """Lower case must not match: normalisation happens in the schema, not the SQL."""
    await live.invite("LIVECODE01")
    before = (await orgs_model.get(live.pool, live.org_a))["member_count"]

    row = await orgs_model.join_with_code(
        live.pool, code=code, auth_id=uuid.uuid4(), email="j@live.invalid", user_name=None
    )

    assert row is None
    assert (await orgs_model.get(live.pool, live.org_a))["member_count"] == before


async def test_live_a_revoked_code_is_dead(live) -> None:
    created = await live.invite("REVOKEDCD1")
    await invites_model.revoke(live.pool, live.org_a, created["id"])

    row = await orgs_model.join_with_code(
        live.pool, code="REVOKEDCD1", auth_id=uuid.uuid4(), email="j@live.invalid", user_name=None
    )

    assert row is None


async def test_live_a_lapsed_code_is_dead(live) -> None:
    """Expiry is enforced on the timestamp, since nothing flips `status`."""
    await live.invite("LAPSEDCOD1", expires_at=datetime.now(UTC) - timedelta(minutes=1))

    row = await orgs_model.join_with_code(
        live.pool, code="LAPSEDCOD1", auth_id=uuid.uuid4(), email="j@live.invalid", user_name=None
    )

    assert row is None


async def test_live_a_never_expiring_code_still_works(live) -> None:
    await live.invite("FOREVERCD1", expires_at=None)

    row = await orgs_model.join_with_code(
        live.pool, code="FOREVERCD1", auth_id=uuid.uuid4(), email="j@live.invalid", user_name=None
    )

    assert row is not None


async def test_live_codes_are_globally_unique(live) -> None:
    """Unique across the table, not per org -- redemption looks up by code alone."""
    await live.invite("SHAREDCODE")

    with pytest.raises(asyncpg.UniqueViolationError):
        await live.invite("SHAREDCODE", org=live.org_b)


async def test_live_revoking_twice_finds_nothing_the_second_time(live) -> None:
    created = await live.invite("TWICECODE1")

    assert await invites_model.revoke(live.pool, live.org_a, created["id"]) is not None
    assert await invites_model.revoke(live.pool, live.org_a, created["id"]) is None


async def test_live_another_orgs_invite_cannot_be_revoked(live) -> None:
    created = await live.invite("OTHERORG01")

    assert await invites_model.revoke(live.pool, live.org_b, created["id"]) is None

    invites = await invites_model.list_for_org(live.pool, live.org_a)
    assert [i["status"] for i in invites] == ["active"]


async def test_live_members_list_admins_first(live) -> None:
    await orgs_model.join_with_code(
        live.pool, code=(await live.invite("MEMBERCOD1"))["code"],
        auth_id=uuid.uuid4(), email="analyst@live.invalid", user_name=None,
    )

    members = await orgs_model.list_members(live.pool, live.org_a)

    assert [m["role"] for m in members] == ["admin", "analyst"]
    assert members[0]["email"] == "admin@live.invalid"


async def test_live_invites_are_scoped_to_their_org(live) -> None:
    await live.invite("ORGACODE01")
    await live.invite("ORGBCODE01", org=live.org_b)

    assert len(await invites_model.list_for_org(live.pool, live.org_a)) == 1
