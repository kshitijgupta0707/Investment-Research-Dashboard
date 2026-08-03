"""Tool definitions exposed to the model during planning.

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

from google.genai import types
from pydantic import BaseModel, Field, field_validator

MARKET_DATA = "get_market_data"
NEWS_SENTIMENT = "get_news_sentiment"
KNOWLEDGE_BASE = "search_knowledge_base"

# Not a data source. Nothing executes it -- the service reads it off the plan and
# answers 400 before any tool runs. It is a tool so that declining stays a model
# decision made through the same mechanism as every other decision, rather than a
# keyword filter bolted onto the query text.
OUT_OF_SCOPE = "reject_out_of_scope"

TOOL_NAMES = (MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE, OUT_OF_SCOPE)

# Companies the seeded filing corpus covers. The model is told this explicitly
# so it does not call the knowledge base for a company we hold nothing on.
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

# for each tool, the model is prompted with a schema of the arguments it should produce.
#  The model is not bound by that schema, so the agent validates the arguments before anything reaches an external provider.
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


class OutOfScopeInput(BaseModel):
    """The model's own wording for why it declined. Shown to the analyst."""

    reason: str


TOOL_INPUTS: dict[str, type[BaseModel]] = {
    MARKET_DATA: MarketDataInput,
    NEWS_SENTIMENT: NewsSentimentInput,
    KNOWLEDGE_BASE: KnowledgeBaseInput,
    OUT_OF_SCOPE: OutOfScopeInput,
}

# Checks that the model's tool call arguments are valid before anything reaches an external provider.
def parse_tool_input(name: str, raw: dict[str, Any]) -> BaseModel:
    """Validate the arguments the model produced for a tool call.

    The model is prompted to follow the schema but is not bound by it, so
    arguments are validated before anything reaches an external provider.
    """
    if name not in TOOL_INPUTS:
        raise ValueError(f"unknown tool '{name}'")
    return TOOL_INPUTS[name].model_validate(raw)


# --- schemas ----------------------------------------------------------------

# It is defining the tools what it is for and what it is not for. 
# The model uses this to decide which tools to call
# LLM response back after analyzing it and tells which tools to call and with what arguments.
def build_tool_schemas(kb_tickers: Sequence[str] = KB_TICKERS) -> list[dict[str, Any]]:
    """Tool definitions as plain JSON Schema.

    Deliberately not in any SDK's own type: the descriptions below are the
    agent's whole routing mechanism and are worth keeping independent of the
    provider. `to_function_declarations` adapts them at the call site.
    """
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
                "Also call this alongside "
                f"{KNOWLEDGE_BASE} when the question compares companies' financial position "
                "or balance sheets: the filings carry the reported line items, and this "
                "supplies the current scale and valuation - market capitalisation, P/E - that "
                "makes those figures comparable across companies.\n\n"
                "Do NOT use this for news, announcements or events - use "
                f"{NEWS_SENTIMENT}. Do NOT use this for qualitative or structural information "
                "such as risk factors, business strategy or competitive positioning - use "
                f"{KNOWLEDGE_BASE}. Do NOT use this to answer general "
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
        {
            "name": OUT_OF_SCOPE,
            "description": (
                "Decline a question this assistant does not cover. Nothing is retrieved and "
                "no report is produced; the analyst is shown your reason and can rephrase.\n\n"
                "Use this only when the question is plainly unrelated to companies, markets, "
                "investing or financial concepts - general knowledge, current affairs, "
                "politics, coding help, personal advice, or chat.\n\n"
                "Do NOT use this for anything finance-adjacent, however loosely: economics, "
                "regulation, accounting, a company you do not recognise, or a term you are "
                "unsure of. Wrongly refusing a legitimate research question is far worse than "
                "answering a borderline one, so when in doubt answer instead of declining.\n\n"
                f"Do NOT use this simply because no data tool fits. A question about what a "
                f"financial term means needs no tools and should be answered directly, not "
                f"refused; only reach for this when the subject itself is off-topic."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": (
                            "One sentence the analyst will see, stating what this assistant "
                            "covers. Address them directly and do not apologise, e.g. 'This "
                            "assistant answers questions about companies, markets and "
                            "financial concepts.'"
                        ),
                    },
                },
                "required": ["reason"],
            },
        },
    ]


TOOL_SCHEMAS: list[dict[str, Any]] = build_tool_schemas()

# It is converting the JSON Schema definitions of the tools into how gemini wants it.
# It is dependent on the model you are using.
def to_function_declarations(
    schemas: Sequence[dict[str, Any]],
) -> list[types.FunctionDeclaration]:
    """Adapt the JSON-Schema definitions above into Gemini's tool type.

    `parameters_json_schema` takes the schema verbatim, so nothing is
    re-expressed here -- the adapter is a rename, which is exactly why the
    definitions are kept provider-neutral.
    """
    return [
        types.FunctionDeclaration(
            name=schema["name"],
            description=schema["description"],
            parameters_json_schema=schema["input_schema"],
        )
        for schema in schemas
    ]



#it is consumed by the planner to tell which tools to call and with what arguments.
def as_tool(schemas: Sequence[dict[str, Any]]) -> types.Tool:
    """Gemini takes one `Tool` carrying many declarations, not many tools."""
    return types.Tool(function_declarations=to_function_declarations(schemas))
