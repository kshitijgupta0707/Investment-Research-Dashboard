"""Market data behind one interface.

yfinance is primary: no API key, no hard daily cap, usable in a live demo.
Alpha Vantage is the documented fallback -- its free tier allows 25 requests a
day, which is unusable as a primary source but fine as a backstop.

Both implement `MarketDataClient`, so swapping providers is configuration
rather than a rewrite, and `FallbackMarketDataClient` can try one then the
other without either knowing the other exists.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

import httpx

from app.integrations.errors import (
    SymbolNotFound,
    UpstreamError,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.schemas.market import MarketSnapshot, PriceHistory, PricePoint
from app.utils.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class MarketDataClient(Protocol):
    """The contract every provider implements."""

    name: str

    async def get_snapshot(self, ticker: str) -> MarketSnapshot: ...

    async def get_history(self, ticker: str, period: str = "3mo") -> PriceHistory: ...


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# --- yfinance ---------------------------------------------------------------


class YFinanceClient:
    """Yahoo Finance via the unofficial yfinance library.

    The library is synchronous and does network IO, so every call is pushed to
    a worker thread and bounded by an explicit timeout. It is also unofficial:
    failures are wrapped rather than trusted to be any particular exception.
    """

    name = "yfinance"

    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout or get_settings().upstream_timeout_seconds

    async def _run(self, func: Any, *args: Any) -> Any:
        try:
            return await asyncio.wait_for(asyncio.to_thread(func, *args), self._timeout)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise UpstreamTimeout(self.name, f"no response within {self._timeout}s") from exc
        except UpstreamError:
            raise
        except Exception as exc:  # unofficial library: anything can surface
            raise UpstreamUnavailable(self.name, str(exc) or exc.__class__.__name__) from exc

    @staticmethod
    def _fetch_info(ticker: str) -> dict[str, Any]:
        import yfinance as yf

        return yf.Ticker(ticker).info or {}

    @staticmethod
    def _fetch_history(ticker: str, period: str) -> list[tuple[Any, float, Any]]:
        import yfinance as yf

        frame = yf.Ticker(ticker).history(period=period, interval="1d")
        return [
            (index.date(), float(row["Close"]), row.get("Volume"))
            for index, row in frame.iterrows()
        ]

    async def get_snapshot(self, ticker: str) -> MarketSnapshot:
        info = await self._run(self._fetch_info, ticker)

        # yfinance returns a near-empty dict for an unknown symbol rather than
        # raising, so absence of any price is how we detect it.
        price = _as_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        if not info or (price is None and not info.get("shortName")):
            raise SymbolNotFound(self.name, f"no data for '{ticker}'")

        epoch = info.get("regularMarketTime")
        as_of = (
            datetime.fromtimestamp(epoch, tz=timezone.utc)
            if isinstance(epoch, (int, float))
            else datetime.now(timezone.utc)
        )

        return MarketSnapshot(
            ticker=ticker.upper(),
            company_name=info.get("shortName") or info.get("longName"),
            currency=info.get("currency"),
            price=price,
            change_percent=_as_float(info.get("regularMarketChangePercent")),
            volume=_as_int(info.get("volume") or info.get("regularMarketVolume")),
            market_cap=_as_float(info.get("marketCap")),
            pe_ratio=_as_float(info.get("trailingPE")),
            eps=_as_float(info.get("trailingEps")),
            fifty_two_week_high=_as_float(info.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_as_float(info.get("fiftyTwoWeekLow")),
            data_as_of=as_of,
            source=self.name,
        )

    async def get_history(self, ticker: str, period: str = "3mo") -> PriceHistory:
        rows = await self._run(self._fetch_history, ticker, period)
        if not rows:
            raise SymbolNotFound(self.name, f"no price history for '{ticker}'")

        points = [PricePoint(date=day, close=close, volume=_as_int(volume)) for day, close, volume in rows]
        return PriceHistory(
            ticker=ticker.upper(),
            period=period,
            points=points,
            data_as_of=datetime.now(timezone.utc),
            source=self.name,
        )


# --- Alpha Vantage ----------------------------------------------------------

_AV_PERIOD_DAYS = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "5y": 1260}

# A snapshot needs two calls, and sent back to back the second is refused as too
# frequent -- measured: consistently throttled at zero delay, consistently fine
# at three seconds. Without this the fallback returns a price and no fundamentals.
_AV_BURST_DELAY_SECONDS = 1.5


class AlphaVantageClient:
    """Alpha Vantage. Free tier: 25 requests/day, 15-minute delayed quotes.

    Rate-limit responses arrive as HTTP 200 with a "Note" or "Information"
    field rather than 429, so the body has to be inspected.
    """

    name = "alpha_vantage"
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.alpha_vantage_api_key
        self._timeout = timeout or settings.upstream_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def _get(self, params: dict[str, str]) -> dict[str, Any]:
        if not self.configured:
            raise UpstreamUnavailable(self.name, "ALPHA_VANTAGE_API_KEY is not set")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.BASE_URL, params={**params, "apikey": self._api_key})
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout(self.name, f"no response within {self._timeout}s") from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(self.name, str(exc)) from exc

        if response.status_code == 429:
            raise UpstreamRateLimited(self.name, "daily quota exhausted")
        if response.status_code >= 500:
            raise UpstreamUnavailable(self.name, f"HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamUnavailable(self.name, "response was not JSON") from exc

        if "Note" in payload or "Information" in payload:
            raise UpstreamRateLimited(self.name, "call frequency limit reached")
        if "Error Message" in payload:
            raise SymbolNotFound(self.name, str(payload["Error Message"]))

        return payload

    async def get_snapshot(self, ticker: str) -> MarketSnapshot:
        quote = (await self._get({"function": "GLOBAL_QUOTE", "symbol": ticker})).get("Global Quote", {})
        if not quote:
            raise SymbolNotFound(self.name, f"no quote for '{ticker}'")

        overview: dict[str, Any] = {}
        try:
            await asyncio.sleep(_AV_BURST_DELAY_SECONDS)
            overview = await self._get({"function": "OVERVIEW", "symbol": ticker})
        except UpstreamError as exc:
            # Fundamentals are a bonus; a quote alone is still useful.
            logger.warning("alpha_vantage overview unavailable for %s: %s", ticker, exc)

        change = quote.get("10. change percent", "").rstrip("%")
        traded_on = quote.get("07. latest trading day")
        as_of = (
            datetime.fromisoformat(traded_on).replace(tzinfo=timezone.utc)
            if traded_on
            else datetime.now(timezone.utc)
        )

        return MarketSnapshot(
            ticker=ticker.upper(),
            company_name=overview.get("Name"),
            currency=overview.get("Currency"),
            price=_as_float(quote.get("05. price")),
            change_percent=_as_float(change),
            volume=_as_int(quote.get("06. volume")),
            market_cap=_as_float(overview.get("MarketCapitalization")),
            pe_ratio=_as_float(overview.get("PERatio")),
            eps=_as_float(overview.get("EPS")),
            fifty_two_week_high=_as_float(overview.get("52WeekHigh")),
            fifty_two_week_low=_as_float(overview.get("52WeekLow")),
            data_as_of=as_of,
            source=self.name,
        )

    async def get_history(self, ticker: str, period: str = "3mo") -> PriceHistory:
        payload = await self._get({"function": "TIME_SERIES_DAILY", "symbol": ticker, "outputsize": "compact"})
        series = payload.get("Time Series (Daily)", {})
        if not series:
            raise SymbolNotFound(self.name, f"no price history for '{ticker}'")

        limit = _AV_PERIOD_DAYS.get(period, 66)
        points = [
            PricePoint(
                date=datetime.fromisoformat(day).date(),
                close=float(values["4. close"]),
                volume=_as_int(values.get("5. volume")),
            )
            for day, values in sorted(series.items())[-limit:]
        ]

        return PriceHistory(
            ticker=ticker.upper(),
            period=period,
            points=points,
            data_as_of=datetime.now(timezone.utc),
            source=self.name,
        )


# --- failover ---------------------------------------------------------------


class FallbackMarketDataClient:
    """Try the primary provider, fall back to the secondary on failure.

    A missing symbol is not retried elsewhere: the ticker is wrong, and the
    fallback would only burn quota to say the same thing.
    """

    name = "market_data"

    def __init__(self, primary: MarketDataClient, fallback: MarketDataClient | None = None) -> None:
        self.primary = primary
        self.fallback = fallback

    async def _attempt(self, method: str, *args: Any) -> Any:
        try:
            return await getattr(self.primary, method)(*args)
        except SymbolNotFound:
            raise
        except UpstreamError as exc:
            if self.fallback is None:
                raise
            logger.warning(
                "%s failed (%s), falling back to %s", self.primary.name, exc, self.fallback.name
            )
            return await getattr(self.fallback, method)(*args)

    async def get_snapshot(self, ticker: str) -> MarketSnapshot:
        return await self._attempt("get_snapshot", ticker)

    async def get_history(self, ticker: str, period: str = "3mo") -> PriceHistory:
        return await self._attempt("get_history", ticker, period)


def build_market_data_client() -> MarketDataClient:
    """Wire the configured providers together."""
    alpha_vantage = AlphaVantageClient()
    return FallbackMarketDataClient(
        primary=YFinanceClient(),
        fallback=alpha_vantage if alpha_vantage.configured else None,
    )
