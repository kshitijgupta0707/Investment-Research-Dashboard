"""Endpoints describing the authenticated caller."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=CurrentUser)
async def read_current_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Return the caller's identity, organization and role."""
    return user
