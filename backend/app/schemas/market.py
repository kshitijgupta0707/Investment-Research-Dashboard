"""Provider-neutral market data.

yfinance and Alpha Vantage return entirely different shapes; both are mapped
into these models so the agent and the frontend never learn which one answered.

Every field is optional except the ticker: free tiers omit fields
unpredictably, and a missing P/E must not fail a whole request.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class MarketSnapshot(BaseModel):
    """A point-in-time view of one company."""

    ticker: str
    company_name: str | None = None
    currency: str | None = None

    price: float | None = None
    change_percent: float | None = None
    volume: int | None = None

    market_cap: float | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    # When the provider says the data was current. Never "now" if the provider
    # tells us otherwise -- quotes on free tiers are delayed, and the UI must
    # be able to say so rather than implying live pricing.
    data_as_of: datetime
    source: str


class PricePoint(BaseModel):
    date: date
    close: float
    volume: int | None = None


class PriceHistory(BaseModel):
    ticker: str
    period: str
    points: list[PricePoint]
    data_as_of: datetime
    source: str
