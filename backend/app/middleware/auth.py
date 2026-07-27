"""JWT verification and tenant context.

Two dependencies, in layers:

* `get_authenticated_identity` -- the token is valid. Nothing more is claimed.
* `get_current_user` -- the token is valid **and** the caller has a membership,
  so an organization and role exist to authorise against.

Almost everything wants the second. Signup wants the first, because a user
creating an organization or redeeming an invite necessarily has no membership
yet, and would otherwise be locked out of the only endpoints that could give
them one.

An invalid or expired token is rejected with 401 by both, before any tenant data
is read. Supabase's `sb_*` keys sign asymmetrically, so verification fetches
public keys from the project's JWKS endpoint rather than sharing a symmetric
secret.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import db
from app.models import users as users_model
from app.schemas.auth import AuthenticatedIdentity, CurrentUser
from app.utils.config import get_settings

_ALGORITHMS = ["ES256", "RS256"]
_AUDIENCE = "authenticated"

# auto_error=False so a missing header yields our 401 rather than FastAPI's 403.
_bearer = HTTPBearer(auto_error=False)

_jwks_client: jwt.PyJWKClient | None = None


def _jwks() -> jwt.PyJWKClient:
    """Cached JWKS client. Fetches signing keys once and reuses them."""
    global _jwks_client
    if _jwks_client is None:
        jwks_url = get_settings().supabase_jwks_url
        if not jwks_url:
            raise RuntimeError("SUPABASE_JWKS_URL is not set.")
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _unauthorised(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode(token: str) -> dict[str, Any]:
    """Verify signature, expiry, audience and issuer.

    Synchronous: PyJWT's JWKS client uses blocking IO on a cache miss, so
    callers run this in a worker thread to keep the event loop free.
    """
    signing_key = _jwks().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=_ALGORITHMS,
        audience=_AUDIENCE,
        issuer=get_settings().supabase_url.rstrip("/") + "/auth/v1",
    )


async def get_authenticated_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedIdentity:
    """Verify the bearer token. Says nothing about membership.

    Depend on this only where a caller legitimately has no organization yet --
    in practice, signup. Everywhere else, use `get_current_user`.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorised("Missing bearer token.")

    try:
        claims = await asyncio.to_thread(_decode, credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorised("Token has expired.") from None
    except (jwt.InvalidTokenError, jwt.PyJWKClientError):
        # Deliberately vague: the specific reason is useful to an attacker.
        raise _unauthorised("Invalid token.") from None

    subject = claims.get("sub")
    if not subject:
        raise _unauthorised("Token is missing the subject claim.")

    try:
        auth_id = UUID(str(subject))
    except ValueError:
        raise _unauthorised("Token subject is not a valid identifier.") from None

    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email")
    return AuthenticatedIdentity(auth_id=auth_id, email=email)


async def get_current_user(
    request: Request,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> CurrentUser:
    """Verify the bearer token and resolve the caller's tenant context."""
    record = await users_model.get_by_auth_id(db.get_pool(), identity.auth_id)
    if record is None:
        # Authenticated by Supabase, but with no membership in this application.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of any organization.",
        )

    user = CurrentUser(
        id=record["id"],
        auth_id=record["supabase_auth_id"],
        email=record["email"],
        org_id=record["org_id"],
        role=record["role"],
    )

    # Shared via the request scope so the access log can report who called.
    request.state.user_id = str(user.id)
    request.state.org_id = str(user.org_id)
    return user
