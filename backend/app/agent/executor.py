"""Running the selected tools concurrently.

Two rules drive the whole module:

* **Tools run in parallel.** A three-tool query costs one tool's latency, not
  three. Multiple tickers within a tool are parallel too.
* **One failure must not lose the rest.** Every tool is isolated behind its own
  timeout and except block; a provider outage degrades the report to `partial`
  rather than failing the request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from app.agent.sentiment import classify_articles
from app.agent.tools import (
    KNOWLEDGE_BASE,
    MARKET_DATA,
    NEWS_SENTIMENT,
    KnowledgeBaseInput,
    MarketDataInput,
    NewsSentimentInput,
    parse_tool_input,
)
from app.integrations.kb_search import search_knowledge_base
from app.integrations.market_data import MarketDataClient, build_market_data_client
from app.integrations.newsapi import NewsAPIClient
from app.schemas.agent import PlannedToolCall, QueryPlan
from app.schemas.execution import ExecutionResult, ToolResult
from app.schemas.news import Article
from app.utils.config import get_settings

logger = logging.getLogger(__name__)


class ToolContext:
    """Dependencies the tools need, injected so tests can substitute them."""

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        market: MarketDataClient | None = None,
        news: NewsAPIClient | None = None,
        classifier: Callable[[list[Article], str], Awaitable[list[Article]]] | None = None,
    ) -> None:
        self.pool = pool
        self.market = market or build_market_data_client()
        self.news = news or NewsAPIClient()
        self.classify = classifier or classify_articles


async def _gather_per_ticker(coros: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Run one coroutine per ticker, keeping whatever succeeds.

    A single unknown ticker in a three-way comparison should not lose the other
    two, so failures are collected rather than raised.
    """
    settled = await asyncio.gather(*coros.values(), return_exceptions=True)

    ok: dict[str, Any] = {}
    failed: list[str] = []
    for ticker, outcome in zip(coros, settled, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning(
                "ticker lookup failed",
                extra={"context": {"ticker": ticker, "error": str(outcome)}},
            )
            failed.append(ticker)
        else:
            ok[ticker] = outcome
    return ok, failed


async def _run_market_data(args: MarketDataInput, ctx: ToolContext) -> dict[str, Any]:
    snapshots, failed = await _gather_per_ticker(
        {t: ctx.market.get_snapshot(t) for t in args.tickers}
    )

    history: dict[str, Any] = {}
    if args.historical and snapshots:
        history, _ = await _gather_per_ticker(
            {t: ctx.market.get_history(t, period="3mo") for t in snapshots}
        )

    if not snapshots:
        raise RuntimeError(f"no market data for any of {', '.join(args.tickers)}")

    return {
        "snapshots": {t: s.model_dump(mode="json") for t, s in snapshots.items()},
        "history": {t: h.model_dump(mode="json") for t, h in history.items()},
        "unavailable_tickers": failed,
    }


async def _run_news(args: NewsSentimentInput, ctx: ToolContext) -> dict[str, Any]:
    results, failed = await _gather_per_ticker(
        {t: ctx.news.get_news(t, days=args.days) for t in args.tickers}
    )

    if not results:
        raise RuntimeError(f"no news for any of {', '.join(args.tickers)}")

    # Classify each ticker's articles in parallel. Sentiment is an enrichment:
    # if it fails, the articles are still returned, just unlabelled.
    classified = await asyncio.gather(
        *(ctx.classify(result.articles, ticker) for ticker, result in results.items()),
        return_exceptions=True,
    )
    for (ticker, result), outcome in zip(list(results.items()), classified, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning(
                "sentiment unavailable for ticker",
                extra={"context": {"ticker": ticker, "error": str(outcome)}},
            )
        else:
            results[ticker] = result.model_copy(update={"articles": outcome})

    return {
        "by_ticker": {t: r.model_dump(mode="json") for t, r in results.items()},
        "unavailable_tickers": failed,
    }


async def _run_knowledge_base(args: KnowledgeBaseInput, ctx: ToolContext) -> dict[str, Any]:
    if ctx.pool is None:
        raise RuntimeError("knowledge base is unavailable: no database connection")

    result = await search_knowledge_base(ctx.pool, args.query, tickers=args.tickers)
    return result.model_dump(mode="json")


_HANDLERS = {
    MARKET_DATA: _run_market_data,
    NEWS_SENTIMENT: _run_news,
    KNOWLEDGE_BASE: _run_knowledge_base,
}


async def _run_one(call: PlannedToolCall, ctx: ToolContext) -> ToolResult:
    """Execute one tool. Never raises -- failures come back as data."""
    started = time.perf_counter()
    timeout = get_settings().tool_timeout_seconds

    def finish(ok: bool, data: Any = None, error: str | None = None) -> ToolResult:
        return ToolResult(
            tool_use_id=call.id,
            name=call.name,
            ok=ok,
            data=data,
            error=error,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    handler = _HANDLERS.get(call.name)
    if handler is None:
        return finish(False, error=f"unknown tool '{call.name}'")

    try:
        args = parse_tool_input(call.name, call.arguments)
        data = await asyncio.wait_for(handler(args, ctx), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        return finish(False, error=f"timed out after {timeout}s")
    except Exception as exc:
        # Deliberately broad: a provider raising something unexpected must
        # degrade this one tool, never the whole query.
        return finish(False, error=str(exc) or exc.__class__.__name__)

    return finish(True, data=data)


async def execute_plan(plan: QueryPlan, ctx: ToolContext | None = None) -> ExecutionResult:
    """Run every selected tool concurrently and collect what came back."""
    if not plan.tool_calls:
        return ExecutionResult()

    context = ctx or ToolContext()
    started = time.perf_counter()

    results = await asyncio.gather(*(_run_one(call, context) for call in plan.tool_calls))

    execution = ExecutionResult(
        results=list(results),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )

    logger.info(
        "executed tools",
        extra={
            "context": {
                "tools_run": [r.name for r in execution.results],
                "failed_tools": execution.failed_tools,
                "partial": execution.partial,
                "execution_latency_ms": execution.latency_ms,
            }
        },
    )
    return execution
