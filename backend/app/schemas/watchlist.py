"""Request and response models for the watchlist."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Long enough for the exchange-suffixed forms a real ticker takes -- `BRK.B`,
# `RY.TO` -- and short enough that free text is rejected before it reaches a
# provider lookup.
MAX_TICKER_CHARS = 12
MAX_COMPANY_NAME_CHARS = 120

_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")


class WatchlistAdd(BaseModel):
    """Pinning a company.

    `company_name` is supplied by the caller rather than looked up here. The
    watchlist is a bookmark list, and resolving a name would mean a market-data
    call on every add -- a request against a rate-limited free tier to render a
    label. It is optional; the UI falls back to the ticker.
    """

    ticker: str = Field(
        max_length=MAX_TICKER_CHARS,
        description="Exchange ticker. Normalised to upper case.",
        examples=["NVDA"],
    )
    company_name: str | None = Field(default=None, max_length=MAX_COMPANY_NAME_CHARS)

    @field_validator("ticker")
    @classmethod
    def _symbol(cls, value: str) -> str:
        """Upper-cased on the way in, so the unique constraint means what it says.

        Without this, `nvda` and `NVDA` are two different rows in the same
        watchlist and the uniqueness guarantee is decorative.
        """
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("ticker must not be blank")
        if not _TICKER.match(symbol):
            raise ValueError("ticker may contain only letters, digits, dots and hyphens")
        return symbol

    @field_validator("company_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        return name or None


class WatchlistEntry(BaseModel):
    id: UUID
    ticker: str
    company_name: str | None
    created_at: datetime
