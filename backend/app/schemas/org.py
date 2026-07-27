"""Request and response models for organization management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import Role

MAX_ORG_NAME_CHARS = 120
MAX_USER_NAME_CHARS = 120

InviteStatus = Literal["active", "revoked", "expired"]


class OrgCreate(BaseModel):
    """Founding an organization. The caller becomes its admin."""

    name: str = Field(min_length=2, max_length=MAX_ORG_NAME_CHARS, examples=["Northwind Capital"])
    user_name: str | None = Field(default=None, max_length=MAX_USER_NAME_CHARS)

    @field_validator("name", "user_name")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed


class OrgJoin(BaseModel):
    """Redeeming an invite code. The caller joins as an analyst."""

    code: str = Field(max_length=64, examples=["7KQP4M2XRT"])
    user_name: str | None = Field(default=None, max_length=MAX_USER_NAME_CHARS)

    @field_validator("code")
    @classmethod
    def _normalise(cls, value: str) -> str:
        """Strip everything a human might add while copying a code by hand.

        Codes get pasted out of chat messages with stray spaces, and read aloud
        with dashes for grouping. Normalising to the stored alphabet here means
        the lookup is an exact index hit rather than a fuzzy match.
        """
        code = "".join(character for character in value.upper() if character.isalnum())
        if not code:
            raise ValueError("code must not be blank")
        return code

    @field_validator("user_name")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class Membership(BaseModel):
    """What provisioning returns: who the caller now is, and where."""

    user_id: UUID
    org_id: UUID
    org_name: str
    role: Role


class Organization(BaseModel):
    id: UUID
    name: str
    member_count: int
    created_at: datetime


class Member(BaseModel):
    id: UUID
    email: str
    name: str | None
    role: Role
    created_at: datetime


class Invite(BaseModel):
    """`status` is stored; `expired` is derived.

    Nothing sweeps the table, so a lapsed invite is still stored as 'active'.
    The derived flag is what a client should read -- and it is exactly the
    condition redemption enforces, kept in one place rather than reimplemented
    in the UI.
    """

    id: UUID
    code: str
    status: InviteStatus
    expires_at: datetime | None
    created_at: datetime
    created_by_email: str
    expired: bool = False
