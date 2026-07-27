"""Role and ownership guards.

No database or network: the guards operate purely on a resolved CurrentUser,
so they are exercised directly and over HTTP with identity stubbed out.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user
from app.middleware.rbac import require_admin, require_owner_or_admin
from app.schemas.auth import CurrentUser

ORG = uuid4()


def user(role: str) -> CurrentUser:
    return CurrentUser(id=uuid4(), auth_id=uuid4(), email=f"{role}@test.invalid", org_id=ORG, role=role)


@pytest.fixture
def admin() -> CurrentUser:
    return user("admin")


@pytest.fixture
def analyst() -> CurrentUser:
    return user("analyst")


def allows(caller: CurrentUser, created_by: UUID) -> bool:
    try:
        require_owner_or_admin(caller, created_by)
        return True
    except HTTPException:
        return False


# --- ownership -------------------------------------------------------------


def test_creator_may_modify_own_record(analyst: CurrentUser) -> None:
    assert allows(analyst, analyst.id)


def test_analyst_may_not_modify_a_colleagues_record(analyst: CurrentUser) -> None:
    assert not allows(analyst, uuid4())


def test_admin_may_modify_anyones_record(admin: CurrentUser) -> None:
    assert allows(admin, uuid4())
    assert allows(admin, admin.id)


def test_ownership_denial_is_403(analyst: CurrentUser) -> None:
    with pytest.raises(HTTPException) as exc:
        require_owner_or_admin(analyst, uuid4())
    assert exc.value.status_code == 403


def test_is_admin_property(admin: CurrentUser, analyst: CurrentUser) -> None:
    assert admin.is_admin
    assert not analyst.is_admin


# --- route dependency ------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.get("/admin-only")
    async def admin_only(caller: CurrentUser = Depends(require_admin)) -> dict[str, str]:
        return {"role": caller.role}

    return TestClient(app)


def test_admin_reaches_admin_route(client: TestClient, admin: CurrentUser) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: admin
    assert client.get("/admin-only").status_code == 200


def test_analyst_is_refused_with_403(client: TestClient, analyst: CurrentUser) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: analyst
    response = client.get("/admin-only")
    assert response.status_code == 403
    assert "admin role" in response.json()["detail"]


def test_anonymous_gets_401_not_403(client: TestClient) -> None:
    """The token is verified before the role, so an unknown caller is 401."""
    client.app.dependency_overrides.clear()
    assert client.get("/admin-only").status_code == 401
