"""Organization management: provisioning, members, invite codes.

Provisioning is the one place in the API where the caller has no tenant yet, so
it is also the one place where `org_id` cannot come from the JWT -- it is either
being created or being read out of an invite. Everything after that point is
org-scoped and admin-gated in the usual way.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.models import audit, org_invites, organizations
from app.schemas.auth import AuthenticatedIdentity, CurrentUser
from app.schemas.org import Invite, Member, Membership, OrgCreate, OrgJoin, Organization

logger = logging.getLogger(__name__)

ACTION_ORG_CREATED = "org.created"
ACTION_MEMBER_JOINED = "org.member_joined"
ACTION_INVITE_CREATED = "invite.created"
ACTION_INVITE_REVOKED = "invite.revoked"

# No I, L, O, U, 0 or 1: codes get read aloud and typed by hand, and those are
# the characters people get wrong. 30 symbols over 10 places is ~49 bits, which
# is not guessable at any rate an HTTP endpoint can be asked questions.
_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
CODE_LENGTH = 10
INVITE_TTL_DAYS = 7

# Collisions are vanishingly unlikely; retrying twice costs nothing and turns a
# freak unique violation into a successful request rather than a 500.
_CODE_ATTEMPTS = 3


def generate_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


def _require_email(identity: AuthenticatedIdentity) -> str:
    """Provisioning needs an address; `users.email` is not nullable."""
    if not identity.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The access token does not carry an email address.",
        )
    return identity.email


def _already_a_member() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This account already belongs to an organization.",
    )


def _to_invite(row: asyncpg.Record) -> Invite:
    data = dict(row)
    expires_at: datetime | None = data.get("expires_at")
    data["expired"] = expires_at is not None and expires_at <= datetime.now(timezone.utc)
    return Invite.model_validate(data)


# --- provisioning -----------------------------------------------------------


async def create_org(
    pool: asyncpg.Pool, identity: AuthenticatedIdentity, payload: OrgCreate
) -> Membership:
    """Found an organization and become its admin."""
    email = _require_email(identity)

    try:
        row = await organizations.create_with_admin(
            pool,
            name=payload.name,
            auth_id=identity.auth_id,
            email=email,
            user_name=payload.user_name,
        )
    except asyncpg.UniqueViolationError:
        # users.supabase_auth_id is unique. Signing up twice is a conflict, not
        # a second organization.
        raise _already_a_member() from None

    membership = Membership.model_validate(dict(row))
    await audit.record(
        pool,
        org_id=membership.org_id,
        user_id=membership.user_id,
        action=ACTION_ORG_CREATED,
        entity_type="organization",
        entity_id=membership.org_id,
        metadata={"name": membership.org_name},
    )
    logger.info("organization created", extra={"context": {"org_id": str(membership.org_id)}})
    return membership


async def join_org(
    pool: asyncpg.Pool, identity: AuthenticatedIdentity, payload: OrgJoin
) -> Membership:
    """Redeem an invite code and join as an analyst."""
    email = _require_email(identity)

    try:
        row = await organizations.join_with_code(
            pool,
            code=payload.code,
            auth_id=identity.auth_id,
            email=email,
            user_name=payload.user_name,
        )
    except asyncpg.UniqueViolationError:
        raise _already_a_member() from None

    if row is None:
        # One answer for wrong, revoked and lapsed alike. Distinguishing them
        # would turn this endpoint into an oracle for guessing live codes.
        logger.warning("invite code rejected", extra={"context": {"auth_id": str(identity.auth_id)}})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That invite code is not valid.",
        )

    membership = Membership.model_validate(dict(row))
    await audit.record(
        pool,
        org_id=membership.org_id,
        user_id=membership.user_id,
        action=ACTION_MEMBER_JOINED,
        entity_type="user",
        entity_id=membership.user_id,
        metadata={"role": membership.role},
    )
    return membership


# --- reading ----------------------------------------------------------------


async def get_org(pool: asyncpg.Pool, user: CurrentUser) -> Organization:
    """The caller's own organization. Any member may read this."""
    row = await organizations.get(pool, user.org_id)
    if row is None:
        # The org_id came from a membership row, so this means the organization
        # was deleted mid-session rather than that the caller guessed an id.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    return Organization.model_validate(dict(row))


async def list_members(pool: asyncpg.Pool, user: CurrentUser) -> list[Member]:
    """Everyone in the caller's organization. Admin-gated at the route."""
    rows = await organizations.list_members(pool, user.org_id)
    return [Member.model_validate(dict(row)) for row in rows]


async def list_invites(pool: asyncpg.Pool, user: CurrentUser) -> list[Invite]:
    rows = await org_invites.list_for_org(pool, user.org_id)
    return [_to_invite(row) for row in rows]


# --- invites ----------------------------------------------------------------


async def create_invite(pool: asyncpg.Pool, user: CurrentUser) -> Invite:
    """Mint an invite code for the caller's organization."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    for attempt in range(_CODE_ATTEMPTS):
        try:
            row = await org_invites.create(
                pool,
                org_id=user.org_id,
                created_by=user.id,
                code=generate_code(),
                expires_at=expires_at,
            )
            break
        except asyncpg.UniqueViolationError:
            if attempt == _CODE_ATTEMPTS - 1:
                raise
            logger.warning("invite code collision, retrying")

    invite = _to_invite(row)
    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_INVITE_CREATED,
        entity_type="org_invite",
        entity_id=invite.id,
        # Deliberately no code: the audit log is org-readable, and a live invite
        # code sitting in it would be a standing way in.
        metadata={"expires_at": invite.expires_at.isoformat() if invite.expires_at else None},
    )
    logger.info("invite created", extra={"context": {"invite_id": str(invite.id)}})
    return invite


async def revoke_invite(pool: asyncpg.Pool, user: CurrentUser, invite_id: UUID) -> Invite:
    """Withdraw a live invite. Another org's id is a 404, not a 403."""
    row = await org_invites.revoke(pool, user.org_id, invite_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active invite with that id.",
        )

    invite = _to_invite(row)
    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_INVITE_REVOKED,
        entity_type="org_invite",
        entity_id=invite.id,
    )
    return invite
