"""Endpoints describing the authenticated caller."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.envelope import Envelope, ok

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=Envelope[CurrentUser])
async def read_current_user(user: CurrentUser = Depends(get_current_user)) -> Envelope[CurrentUser]:
    """Return the caller's identity, organization and role."""
    return ok(user)
