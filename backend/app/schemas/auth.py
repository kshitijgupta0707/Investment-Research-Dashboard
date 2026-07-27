"""Identity of the authenticated caller."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "analyst"]


class CurrentUser(BaseModel):
    """Resolved from the JWT plus the matching row in `users`.

    `id` is our own primary key; `auth_id` is the Supabase Auth id carried in
    the token's `sub` claim. Foreign keys elsewhere reference `id`.
    """

    id: UUID
    auth_id: UUID
    email: str
    org_id: UUID
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
