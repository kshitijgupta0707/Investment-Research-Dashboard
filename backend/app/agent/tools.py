"""Tool definitions exposed to Claude during planning.

These descriptions are the entire mechanism by which the agent decides which
data sources a question needs. There is no keyword routing anywhere in the
codebase -- the model reads these and chooses, per query.

Because of that, each description states both what the tool is *for* and, just
as importantly, what it is *not* for, with a pointer to the tool that does
cover that case. Without the negative guidance the model reaches for every tool
on every question, which defeats the purpose: "what's the latest news on Tesla?"
must not trigger a market data call.
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, Field, field_validator

MARKET_DATA = "get_market_data"
NEWS_SENTIMENT = "get_news_sentiment"
KNOWLEDGE_BASE = "search_knowledge_base"

TOOL_NAMES = (MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE)

# Companies the seeded filing corpus covers. Claude is told this explicitly so
# it does not call the knowledge base for a company we hold nothing on.
KB_TICKERS: tuple[str, ...] = ("NVDA", "AMD", "INTC", "TSLA", "JPM", "GS", "MS")


# --- validated inputs -------------------------------------------------------


def _normalise_tickers(value: list[str] | None) -> list[str] | None:
    """Uppercase and de-duplicate while preserving order.

    The model may emit "nvda", "NVDA " or repeat a symbol across a comparison.
    """
    if value is None:
        return None
    seen: dict[str, None] = {}
    for raw in value:
        symbol = raw.strip().upper()
        if symbol:
            seen.setdefault(symbol, None)
    return list(seen)


class _TickerInput(BaseModel):
    """Shared ticker cleaning. The validator applies wherever the field exists."""

    @field_validator("tickers", check_fields=False)
    @classmethod
    def clean_tickers(cls, value: list[str] | None) -> list[str] | None:
        return _normalise_tickers(value)


class MarketDataInput(_TickerInput):
    tickers: list[str]
    metrics: list[str] | None = None
    historical: bool = False


class NewsSentimentInput(_TickerInput):
    tickers: list[str]
    days: int = Field(default=30, ge=1, le=90)


class KnowledgeBaseInput(_TickerInput):
    query: str
    tickers: list[str] | None = None


TOOL_INPUTS: dict[str, type[BaseModel]] = {
    MARKET_DATA: MarketDataInput,
    NEWS_SENTIMENT: NewsSentimentInput,
    KNOWLEDGE_BASE: KnowledgeBaseInput,
}


def parse_tool_input(name: str, raw: dict[str, Any]) -> BaseModel:
    """Validate the arguments Claude produced for a tool call.

    The model is prompted to follow the schema but is not bound by it, so
    arguments are validated before anything reaches an external provider.
    """
    if name not in TOOL_INPUTS:
        raise ValueError(f"unknown tool '{name}'")
    return TOOL_INPUTS[name].model_validate(raw)


# --- schemas ----------------------------------------------------------------


def build_tool_schemas(kb_tickers: Sequence[str] = KB_TICKERS) -> list[dict[str, Any]]:
    """Tool definitions in Anthropic tool-use format."""
    covered = ", ".join(kb_tickers)

    return [
        {
            "name": MARKET_DATA,
            "description": (
                "Fetch current quantitative market data for one or more publicly traded "
                "companies: latest share price, percentage change, trading volume, market "
                "capitalisation, P/E ratio, EPS, and 52-week high and low. Can also return a "
                "daily historical price series for charting performance over time.\n\n"
                "Use this when the question asks about price, valuation, market cap, trading "
                "multiples, or how a stock has performed over a period.\n\n"
                "Do NOT use this for news, announcements or events - use "
                f"{NEWS_SENTIMENT}. Do NOT use this for qualitative or structural information "
                "such as risk factors, business strategy, competitive positioning or balance "
                f"sheet composition - use {KNOWLEDGE_BASE}. Do NOT use this to answer general "
                "finance questions that require no company-specific data, such as explaining "
                "what a financial ratio means; answer those directly instead."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Stock ticker symbols, e.g. ['NVDA', 'AMD']. Include every company "
                            "the question compares."
                        ),
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional subset of metrics of interest, e.g. ['pe_ratio', "
                            "'market_cap']. Omit to return all available metrics."
                        ),
                    },
                    "historical": {
                        "type": "boolean",
                        "description": (
                            "Set true when the question concerns performance over time, a trend, "
                            "or anything that would be shown as a price chart. Leave false for a "
                            "point-in-time quote."
                        ),
                    },
                },
                "required": ["tickers"],
            },
        },
        {
            "name": NEWS_SENTIMENT,
            "description": (
                "Fetch recent news articles about one or more publicly traded companies and "
                "classify the sentiment of each article as positive, negative or neutral.\n\n"
                "Use this when the question asks what is happening with a company, recent "
                "developments, announcements, headlines, coverage, market reaction or "
                "sentiment.\n\n"
                f"Do NOT use this for numeric market data such as price or P/E - use "
                f"{MARKET_DATA}. Do NOT use this for long-term or structural information that "
                f"would appear in a regulatory filing - use {KNOWLEDGE_BASE}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Stock ticker symbols to fetch news for, e.g. ['TSLA'].",
                    },
                    "days": {
                        "type": "integer",
                        "description": (
                            "How many days back to search, 1 to 90. Defaults to 30. Use a "
                            "smaller window when the question emphasises very recent events."
                        ),
                    },
                },
                "required": ["tickers"],
            },
        },
        {
            "name": KNOWLEDGE_BASE,
            "description": (
                "Search a corpus of company filing excerpts covering business overview, risk "
                "factors, management's discussion of results, and competitive landscape.\n\n"
                "Use this when the question asks about risks, competitive threats or "
                "positioning, business strategy, balance sheet composition, capital ratios, or "
                "any other qualitative or structural information that a company filing would "
                "contain rather than a price feed.\n\n"
                f"The corpus covers only these companies: {covered}. Do NOT call this tool for "
                "any other company - there is nothing to find, and the call wastes a step.\n\n"
                f"Do NOT use this for current price or valuation - use {MARKET_DATA}. Do NOT "
                f"use this for recent news or events - use {NEWS_SENTIMENT}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search terms describing the information needed, e.g. 'supply chain "
                            "concentration risk' or 'capital ratios and deposits'. Use the "
                            "vocabulary a filing would use, not the user's exact wording."
                        ),
                    },
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional. Restrict the search to these companies. Omit to search "
                            "the whole corpus."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    ]


TOOL_SCHEMAS: list[dict[str, Any]] = build_tool_schemas()
