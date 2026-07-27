"""Organization endpoints.

Three access levels on one router, which is the point of the CR:

* **Any verified token** -- the two provisioning endpoints. A caller with no
  membership must be able to reach these, or they can never get one.
* **Any member** -- reading your own organization.
* **Admin only** -- the member list and everything to do with invites, enforced
  by `require_admin` rather than by hiding buttons.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app import db
from app.middleware.auth import get_authenticated_identity, get_current_user
from app.middleware.rbac import require_admin
from app.schemas.auth import AuthenticatedIdentity, CurrentUser
from app.schemas.envelope import Envelope, ok
from app.schemas.org import Invite, Member, Membership, OrgCreate, OrgJoin, Organization
from app.services import org as org_service

router = APIRouter(prefix="/api/org", tags=["organization"])


# --- provisioning -----------------------------------------------------------


@router.post("", response_model=Envelope[Membership], status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> Envelope[Membership]:
    """Found an organization. The caller becomes its admin.

    Depends on the identity rather than on `get_current_user`: the caller has
    no membership yet, which is precisely why they are here.
    """
    return ok(await org_service.create_org(db.get_pool(), identity, body))


@router.post("/join", response_model=Envelope[Membership], status_code=status.HTTP_201_CREATED)
async def join_organization(
    body: OrgJoin,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> Envelope[Membership]:
    """Redeem an invite code, joining as an analyst."""
    return ok(await org_service.join_org(db.get_pool(), identity, body))


# --- membership -------------------------------------------------------------


@router.get("", response_model=Envelope[Organization])
async def read_organization(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[Organization]:
    """The caller's own organization. Any member may read this."""
    return ok(await org_service.get_org(db.get_pool(), user))


@router.get("/members", response_model=Envelope[list[Member]])
async def list_members(user: CurrentUser = Depends(require_admin)) -> Envelope[list[Member]]:
    """Everyone in the organization. Admins first. Admin only."""
    return ok(await org_service.list_members(db.get_pool(), user))


# --- invites ----------------------------------------------------------------


@router.post("/invites", response_model=Envelope[Invite], status_code=status.HTTP_201_CREATED)
async def create_invite(user: CurrentUser = Depends(require_admin)) -> Envelope[Invite]:
    """Mint an invite code. Admin only.

    Takes no body: the code, its organization and its lifetime are all decided
    server-side. Letting a client propose a code would let it pick a guessable
    one.
    """
    return ok(await org_service.create_invite(db.get_pool(), user))


@router.get("/invites", response_model=Envelope[list[Invite]])
async def list_invites(user: CurrentUser = Depends(require_admin)) -> Envelope[list[Invite]]:
    """The organization's invites, newest first. Admin only."""
    return ok(await org_service.list_invites(db.get_pool(), user))


@router.delete("/invites/{invite_id}", response_model=Envelope[Invite])
async def revoke_invite(
    invite_id: UUID,
    user: CurrentUser = Depends(require_admin),
) -> Envelope[Invite]:
    """Withdraw a live invite. Admin only.

    Returns the updated invite rather than a bodyless 204, so the client can
    re-render the row it just changed without a second request.
    """
    return ok(await org_service.revoke_invite(db.get_pool(), user, invite_id))
