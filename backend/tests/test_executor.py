"""Parallel tool execution and graceful degradation.

The behaviour that matters here is what happens when things go wrong: a tool
failing, timing out, or returning nothing must degrade the report rather than
fail the request.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from app.agent.executor import ToolContext, execute_plan
from app.agent.tools import KNOWLEDGE_BASE, MARKET_DATA, NEWS_SENTIMENT
from app.integrations.errors import UpstreamRateLimited, UpstreamTimeout
from app.schemas.agent import PlannedToolCall, QueryPlan
from app.schemas.market import MarketSnapshot, PriceHistory
from app.schemas.news import Article, NewsResult

# --- stubs ------------------------------------------------------------------


def snapshot(ticker: str) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker, price=100.0, data_as_of=datetime.now(timezone.utc), source="stub"
    )


def news(ticker: str) -> NewsResult:
    return NewsResult(
        ticker=ticker,
        query=f"{ticker} stock",
        articles=[
            Article(
                title=f"{ticker} rises",
                url="https://example.com/a",
                source="Reuters",
                published_at=datetime.now(timezone.utc),
            )
        ],
        data_as_of=datetime.now(timezone.utc),
    )


class StubMarket:
    name = "stub-market"

    def __init__(self, fail: set[str] | None = None, delay: float = 0.0) -> None:
        self.fail = fail or set()
        self.delay = delay
        self.calls: list[str] = []

    async def get_snapshot(self, ticker: str) -> MarketSnapshot:
        self.calls.append(ticker)
        if self.delay:
            await asyncio.sleep(self.delay)
        if ticker in self.fail:
            raise UpstreamRateLimited("stub-market", "quota")
        return snapshot(ticker)

    async def get_history(self, ticker: str, period: str = "3mo") -> PriceHistory:
        return PriceHistory(
            ticker=ticker, period=period, points=[], data_as_of=datetime.now(timezone.utc), source="stub"
        )


class StubNews:
    def __init__(self, fail: set[str] | None = None, delay: float = 0.0) -> None:
        self.fail = fail or set()
        self.delay = delay

    async def get_news(self, ticker: str, company_name: str | None = None, days: int = 30, limit: int = 10) -> NewsResult:
        if self.delay:
            await asyncio.sleep(self.delay)
        if ticker in self.fail:
            raise UpstreamTimeout("newsapi", "slow")
        return news(ticker)


async def passthrough(articles: list[Article], ticker: str) -> list[Article]:
    """Sentiment is exercised in test_sentiment.py; here it must not call out."""
    return articles


def context(**kwargs: Any) -> ToolContext:
    kwargs.setdefault("market", StubMarket())
    kwargs.setdefault("news", StubNews())
    kwargs.setdefault("classifier", passthrough)
    return ToolContext(**kwargs)


def plan(*calls: tuple[str, dict[str, Any]]) -> QueryPlan:
    return QueryPlan(
        query="test",
        model="stub",
        tool_calls=[
            PlannedToolCall(id=f"toolu_{i}", name=name, arguments=args)
            for i, (name, args) in enumerate(calls)
        ],
    )


# --- happy path -------------------------------------------------------------


async def test_no_tools_returns_empty_result() -> None:
    """A question answered directly runs nothing."""
    result = await execute_plan(QueryPlan(query="what is a P/E ratio?", model="stub"))
    assert result.results == []
    assert not result.partial and not result.all_failed


async def test_single_tool_succeeds() -> None:
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), context())

    assert len(result.results) == 1
    assert result.results[0].ok
    assert result.results[0].data["snapshots"]["NVDA"]["price"] == 100.0
    assert not result.partial


async def test_tool_use_id_is_preserved() -> None:
    """Turn 2 matches results to requests by this id."""
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), context())
    assert result.results[0].tool_use_id == "toolu_0"


async def test_historical_data_is_fetched_only_when_asked() -> None:
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), context())
    assert result.results[0].data["history"] == {}

    result = await execute_plan(
        plan((MARKET_DATA, {"tickers": ["NVDA"], "historical": True})), context()
    )
    assert "NVDA" in result.results[0].data["history"]


# --- concurrency ------------------------------------------------------------


async def test_tools_run_in_parallel_not_in_series() -> None:
    """Three slow tools should cost one tool's latency, not three."""
    ctx = context(market=StubMarket(delay=0.3), news=StubNews(delay=0.3))
    started = asyncio.get_event_loop().time()

    await execute_plan(
        plan(
            (MARKET_DATA, {"tickers": ["NVDA"]}),
            (NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        ),
        ctx,
    )

    elapsed = asyncio.get_event_loop().time() - started
    assert elapsed < 0.55, f"took {elapsed:.2f}s -- looks sequential"


async def test_tickers_within_a_tool_run_in_parallel() -> None:
    ctx = context(market=StubMarket(delay=0.3), news=StubNews())
    started = asyncio.get_event_loop().time()

    await execute_plan(plan((MARKET_DATA, {"tickers": ["JPM", "GS", "MS"]})), ctx)

    elapsed = asyncio.get_event_loop().time() - started
    assert elapsed < 0.55, f"took {elapsed:.2f}s for 3 tickers -- looks sequential"


# --- graceful degradation ---------------------------------------------------


async def test_one_failing_tool_does_not_lose_the_others() -> None:
    """The core requirement: partial results beat no results."""
    ctx = context(market=StubMarket(fail={"NVDA"}), news=StubNews())

    result = await execute_plan(
        plan(
            (MARKET_DATA, {"tickers": ["NVDA"]}),
            (NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        ),
        ctx,
    )

    assert result.partial
    assert result.failed_tools == [MARKET_DATA]
    assert [r.name for r in result.succeeded] == [NEWS_SENTIMENT]


async def test_failure_reason_is_captured() -> None:
    ctx = context(market=StubMarket(fail={"NVDA"}), news=StubNews())
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), ctx)

    assert result.results[0].failed
    assert "no market data" in result.results[0].error


async def test_one_bad_ticker_keeps_the_others() -> None:
    """A three-way comparison should survive one unknown symbol."""
    ctx = context(market=StubMarket(fail={"GS"}), news=StubNews())

    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["JPM", "GS", "MS"]})), ctx)

    assert result.results[0].ok
    assert set(result.results[0].data["snapshots"]) == {"JPM", "MS"}
    assert result.results[0].data["unavailable_tickers"] == ["GS"]


async def test_tool_fails_only_when_every_ticker_fails() -> None:
    ctx = context(market=StubMarket(fail={"JPM", "GS"}), news=StubNews())
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["JPM", "GS"]})), ctx)

    assert result.results[0].failed
    assert result.all_failed


async def test_timeout_is_reported_as_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent import executor

    settings = executor.get_settings()
    monkeypatch.setattr(settings, "tool_timeout_seconds", 0.05)
    ctx = context(market=StubMarket(delay=1.0), news=StubNews())

    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), ctx)

    assert result.results[0].failed
    assert "timed out" in result.results[0].error


async def test_a_slow_tool_does_not_delay_a_fast_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The timeout is per tool, so news still returns while market data hangs."""
    from app.agent import executor

    monkeypatch.setattr(executor.get_settings(), "tool_timeout_seconds", 0.2)
    ctx = context(market=StubMarket(delay=5.0), news=StubNews())

    result = await execute_plan(
        plan(
            (MARKET_DATA, {"tickers": ["NVDA"]}),
            (NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        ),
        ctx,
    )

    assert result.partial
    assert [r.name for r in result.succeeded] == [NEWS_SENTIMENT]


async def test_unexpected_exception_is_contained() -> None:
    """A provider raising something we never anticipated must not 500."""

    class Exploding:
        name = "boom"

        async def get_snapshot(self, ticker: str):
            raise ZeroDivisionError("something absurd")

        async def get_history(self, ticker: str, period: str = "3mo"):
            raise ZeroDivisionError("something absurd")

    ctx = context(market=Exploding(), news=StubNews())
    result = await execute_plan(plan((MARKET_DATA, {"tickers": ["NVDA"]})), ctx)

    assert result.results[0].failed


async def test_knowledge_base_without_a_database_degrades() -> None:
    ctx = context(pool=None, market=StubMarket(), news=StubNews())
    result = await execute_plan(plan((KNOWLEDGE_BASE, {"query": "risks"})), ctx)

    assert result.results[0].failed
    assert "database" in result.results[0].error


async def test_unknown_tool_is_reported_not_raised() -> None:
    result = await execute_plan(plan(("get_weather", {"city": "Paris"})), context())
    assert result.results[0].failed
    assert "unknown tool" in result.results[0].error


async def test_invalid_arguments_fail_only_that_tool() -> None:
    result = await execute_plan(
        plan(
            (MARKET_DATA, {"tickers": "NVDA"}),  # string, not a list
            (NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        ),
        context(),
    )

    assert result.partial
    assert result.failed_tools == [MARKET_DATA]


# --- partial vs total failure ----------------------------------------------


async def test_partial_is_false_when_everything_works() -> None:
    result = await execute_plan(plan((NEWS_SENTIMENT, {"tickers": ["NVDA"]})), context())
    assert not result.partial and not result.all_failed


async def test_partial_is_false_when_everything_fails() -> None:
    """Total failure is a different state from partial, and the UI shows it differently."""
    ctx = context(market=StubMarket(fail={"NVDA"}), news=StubNews(fail={"NVDA"}))

    result = await execute_plan(
        plan(
            (MARKET_DATA, {"tickers": ["NVDA"]}),
            (NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        ),
        ctx,
    )

    assert result.all_failed
    assert not result.partial
    assert set(result.failed_tools) == {MARKET_DATA, NEWS_SENTIMENT}


# --- sentiment is an enrichment, not a dependency ---------------------------


async def test_sentiment_labels_reach_the_news_result() -> None:
    async def label_positive(articles: list[Article], ticker: str) -> list[Article]:
        return [a.model_copy(update={"sentiment": "positive"}) for a in articles]

    result = await execute_plan(
        plan((NEWS_SENTIMENT, {"tickers": ["NVDA"]})), context(classifier=label_positive)
    )

    articles = result.results[0].data["by_ticker"]["NVDA"]["articles"]
    assert articles[0]["sentiment"] == "positive"


async def test_failed_classification_still_returns_the_articles() -> None:
    """Losing the badge must not lose the news."""

    async def explode(articles: list[Article], ticker: str) -> list[Article]:
        raise RuntimeError("classifier down")

    result = await execute_plan(
        plan((NEWS_SENTIMENT, {"tickers": ["NVDA"]})), context(classifier=explode)
    )

    assert result.results[0].ok, "news must survive a sentiment failure"
    articles = result.results[0].data["by_ticker"]["NVDA"]["articles"]
    assert len(articles) == 1
    assert articles[0]["sentiment"] is None
