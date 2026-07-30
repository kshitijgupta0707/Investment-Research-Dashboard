"""External data clients.

Unit tests cover failover and parsing with no network. Tests marked
integration hit the real providers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.integrations.errors import (
    SymbolNotFound,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.integrations.market_data import (
    AlphaVantageClient,
    FallbackMarketDataClient,
    YFinanceClient,
)
from app.integrations.newsapi import NewsAPIClient
from app.schemas.market import MarketSnapshot

# --- stubs ------------------------------------------------------------------


def snapshot(source: str) -> MarketSnapshot:
    return MarketSnapshot(ticker="TEST", price=1.0, data_as_of=datetime.now(timezone.utc), source=source)


class StubClient:
    def __init__(self, name: str, raises: Exception | None = None) -> None:
        self.name = name
        self.raises = raises
        self.calls = 0

    async def get_snapshot(self, ticker: str) -> MarketSnapshot:
        self.calls += 1
        if self.raises:
            raise self.raises
        return snapshot(self.name)

    async def get_history(self, ticker: str, period: str = "3mo"):
        self.calls += 1
        if self.raises:
            raise self.raises
        raise AssertionError("not needed")


# --- failover ---------------------------------------------------------------


async def test_primary_success_does_not_touch_the_fallback() -> None:
    primary, fallback = StubClient("primary"), StubClient("fallback")
    result = await FallbackMarketDataClient(primary, fallback).get_snapshot("NVDA")

    assert result.source == "primary"
    assert fallback.calls == 0, "fallback quota must not be spent when the primary works"


async def test_provider_failure_falls_back() -> None:
    primary = StubClient("primary", raises=UpstreamUnavailable("primary", "down"))
    fallback = StubClient("fallback")

    result = await FallbackMarketDataClient(primary, fallback).get_snapshot("NVDA")
    assert result.source == "fallback"


async def test_rate_limit_falls_back() -> None:
    primary = StubClient("primary", raises=UpstreamRateLimited("primary", "quota"))
    fallback = StubClient("fallback")

    assert (await FallbackMarketDataClient(primary, fallback).get_snapshot("NVDA")).source == "fallback"


async def test_unknown_symbol_is_not_retried_elsewhere() -> None:
    """The ticker is wrong; the fallback would burn quota to say the same."""
    primary = StubClient("primary", raises=SymbolNotFound("primary", "no such ticker"))
    fallback = StubClient("fallback")

    with pytest.raises(SymbolNotFound):
        await FallbackMarketDataClient(primary, fallback).get_snapshot("NOPE")
    assert fallback.calls == 0


async def test_failure_propagates_when_no_fallback_configured() -> None:
    primary = StubClient("primary", raises=UpstreamUnavailable("primary", "down"))

    with pytest.raises(UpstreamUnavailable):
        await FallbackMarketDataClient(primary, None).get_snapshot("NVDA")


# --- configuration guards ---------------------------------------------------


async def test_alpha_vantage_without_a_key_reports_unavailable() -> None:
    client = AlphaVantageClient(api_key="")
    assert not client.configured
    with pytest.raises(UpstreamUnavailable):
        await client.get_snapshot("NVDA")


async def test_newsapi_without_a_key_reports_unavailable() -> None:
    with pytest.raises(UpstreamUnavailable):
        await NewsAPIClient(api_key="").get_news("NVDA")


# --- news parsing -----------------------------------------------------------


def test_query_narrows_to_finance_coverage() -> None:
    query = NewsAPIClient.build_query("NVDA", "NVIDIA Corporation")
    assert '"NVIDIA Corporation"' in query
    assert "earnings" in query


def test_query_falls_back_to_the_ticker() -> None:
    assert NewsAPIClient.build_query("NVDA").startswith("NVDA")


@pytest.mark.parametrize(
    "raw",
    [
        {"title": "[Removed]", "url": "https://x.io", "publishedAt": "2026-01-01T00:00:00Z"},
        {"title": "No url", "url": "", "publishedAt": "2026-01-01T00:00:00Z"},
        {"title": "Bad date", "url": "https://x.io", "publishedAt": "not-a-date"},
        {"title": "", "url": "https://x.io", "publishedAt": "2026-01-01T00:00:00Z"},
    ],
)
def test_unusable_articles_are_skipped(raw: dict) -> None:
    """One malformed entry must not fail the whole batch."""
    assert NewsAPIClient._to_article(raw) is None


def test_valid_article_is_parsed() -> None:
    article = NewsAPIClient._to_article(
        {
            "title": "NVIDIA beats estimates",
            "description": "Revenue up",
            "url": "https://example.com/a",
            "publishedAt": "2026-01-15T09:30:00Z",
            "source": {"name": "Reuters"},
        }
    )
    assert article is not None
    assert article.source == "Reuters"
    assert article.published_at.year == 2026


# --- live providers ---------------------------------------------------------


@pytest.mark.integration
async def test_yfinance_returns_a_real_snapshot() -> None:
    result = await YFinanceClient().get_snapshot("NVDA")

    assert result.ticker == "NVDA"
    assert result.company_name and "NVIDIA" in result.company_name
    assert result.price and result.price > 0
    assert result.market_cap and result.market_cap > 0
    assert result.source == "yfinance"
    assert result.data_as_of.tzinfo is not None, "data_as_of must be timezone-aware"


@pytest.mark.integration
async def test_yfinance_returns_price_history() -> None:
    history = await YFinanceClient().get_history("NVDA", period="1mo")

    assert len(history.points) > 5
    assert all(point.close > 0 for point in history.points)
    assert history.points == sorted(history.points, key=lambda p: p.date), "must be chronological"


@pytest.mark.integration
async def test_yfinance_unknown_symbol_raises_not_found() -> None:
    with pytest.raises(SymbolNotFound):
        await YFinanceClient().get_snapshot("ZZZZ-NOT-A-TICKER")


@pytest.mark.integration
async def test_yfinance_respects_its_timeout() -> None:
    with pytest.raises(UpstreamTimeout):
        await YFinanceClient(timeout=0.001).get_snapshot("NVDA")


@pytest.mark.integration
async def test_newsapi_returns_recent_articles(settings) -> None:
    if not settings.newsapi_api_key:
        pytest.skip("NEWSAPI_API_KEY is not configured")

    result = await NewsAPIClient().get_news("NVDA", company_name="NVIDIA", days=14, limit=5)

    assert result.articles, "expected at least one article"
    assert len(result.articles) <= 5
    for article in result.articles:
        assert article.title and article.url.startswith("http")
        assert article.published_at.tzinfo is not None
