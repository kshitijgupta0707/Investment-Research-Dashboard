"""Identity of the authenticated caller."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "analyst"]


class AuthenticatedIdentity(BaseModel):
    """A verified Supabase token, before any membership is known.

    This is what signup sees: the caller has proved who they are, but has no
    `users` row, no organization and no role yet. Every other endpoint wants
    `CurrentUser` instead -- a caller with no membership has no tenant, and so
    nothing to be authorised against.

    `email` is optional because it is only needed on the provisioning path.
    Everywhere else the address is read from the database, so a token without
    the claim must not break an otherwise valid session.
    """

    auth_id: UUID
    email: str | None = None


class CurrentUser(BaseModel):
    """Resolved from the JWT plus the matching row in `users`.

    `id` is our own primary key; `auth_id` is the Supabase Auth id carried in
    the token's `sub` claim. Foreign keys elsewhere reference `id`.
    """

    id: UUID
    auth_id: UUID
    email: str
    # Optional because signup does not require it -- a user who joined with only
    # an address has no name, and the UI falls back to the address.
    name: str | None = None
    org_id: UUID
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
