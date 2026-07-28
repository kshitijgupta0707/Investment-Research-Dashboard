"""Tool schemas and input validation.

The schemas are what the model reads when choosing tools, so these tests guard
their structure and the guidance the descriptions must carry. Whether the
model actually chooses correctly is tested against the acceptance queries in
the planner tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.tools import (
    KB_TICKERS,
    KNOWLEDGE_BASE,
    MARKET_DATA,
    NEWS_SENTIMENT,
    TOOL_NAMES,
    TOOL_SCHEMAS,
    KnowledgeBaseInput,
    MarketDataInput,
    NewsSentimentInput,
    build_tool_schemas,
    parse_tool_input,
)

BY_NAME = {schema["name"]: schema for schema in TOOL_SCHEMAS}


# --- structure --------------------------------------------------------------


def test_exactly_three_tools_are_exposed() -> None:
    assert len(TOOL_SCHEMAS) == 3
    assert set(BY_NAME) == set(TOOL_NAMES)


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_schema_is_valid_tool_use_format(name: str) -> None:
    schema = BY_NAME[name]
    assert schema["description"].strip()
    assert schema["input_schema"]["type"] == "object"
    assert schema["input_schema"]["properties"]
    assert isinstance(schema["input_schema"]["required"], list)


@pytest.mark.parametrize(
    ("name", "required"),
    [(MARKET_DATA, ["tickers"]), (NEWS_SENTIMENT, ["tickers"]), (KNOWLEDGE_BASE, ["query"])],
)
def test_required_arguments(name: str, required: list[str]) -> None:
    assert BY_NAME[name]["input_schema"]["required"] == required


# --- the guidance that drives selection -------------------------------------


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_each_description_says_what_it_is_not_for(name: str) -> None:
    """Without negative guidance the model calls every tool on every query."""
    assert "Do NOT use this for" in BY_NAME[name]["description"]


@pytest.mark.parametrize(
    ("name", "must_point_at"),
    [
        (MARKET_DATA, [NEWS_SENTIMENT, KNOWLEDGE_BASE]),
        (NEWS_SENTIMENT, [MARKET_DATA, KNOWLEDGE_BASE]),
        (KNOWLEDGE_BASE, [MARKET_DATA, NEWS_SENTIMENT]),
    ],
)
def test_each_description_redirects_to_the_other_tools(name: str, must_point_at: list[str]) -> None:
    """Saying 'not this one' is only useful alongside 'that one instead'."""
    description = BY_NAME[name]["description"]
    for other in must_point_at:
        assert other in description


def test_market_data_discourages_use_for_general_questions() -> None:
    """'What is a P/E ratio?' must select no tools at all."""
    assert "no company-specific data" in BY_NAME[MARKET_DATA]["description"]


def test_knowledge_base_lists_the_companies_it_covers() -> None:
    description = BY_NAME[KNOWLEDGE_BASE]["description"]
    for ticker in KB_TICKERS:
        assert ticker in description


def test_knowledge_base_coverage_can_be_rebuilt_from_live_data() -> None:
    """The corpus is the source of truth; the schema should follow it."""
    schemas = {s["name"]: s for s in build_tool_schemas(["AAPL", "MSFT"])}
    description = schemas[KNOWLEDGE_BASE]["description"]
    assert "AAPL, MSFT" in description
    assert "NVDA" not in description


def test_historical_flag_is_explained_in_terms_of_intent() -> None:
    """The model has to infer it from the question, not from a field name."""
    field = BY_NAME[MARKET_DATA]["input_schema"]["properties"]["historical"]
    assert "over time" in field["description"]


# --- input validation -------------------------------------------------------


def test_tickers_are_uppercased_and_deduplicated() -> None:
    parsed = MarketDataInput(tickers=["nvda", "NVDA ", "amd"])
    assert parsed.tickers == ["NVDA", "AMD"]


def test_ticker_order_is_preserved() -> None:
    """Comparison tables should follow the order the question asked in."""
    assert NewsSentimentInput(tickers=["jpm", "gs", "ms"]).tickers == ["JPM", "GS", "MS"]


def test_defaults_are_applied() -> None:
    assert NewsSentimentInput(tickers=["TSLA"]).days == 30
    assert MarketDataInput(tickers=["NVDA"]).historical is False
    assert KnowledgeBaseInput(query="risks").tickers is None


@pytest.mark.parametrize("days", [0, 91, -5])
def test_out_of_range_day_windows_are_rejected(days: int) -> None:
    with pytest.raises(ValidationError):
        NewsSentimentInput(tickers=["TSLA"], days=days)


def test_missing_required_argument_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MarketDataInput()


def test_parse_tool_input_dispatches_by_name() -> None:
    parsed = parse_tool_input(KNOWLEDGE_BASE, {"query": "capital ratios", "tickers": ["jpm"]})
    assert isinstance(parsed, KnowledgeBaseInput)
    assert parsed.tickers == ["JPM"]


def test_unknown_tool_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_tool_input("get_weather", {})


def test_malformed_arguments_are_rejected_before_reaching_a_provider() -> None:
    """The model is prompted to follow the schema but is not bound by it."""
    with pytest.raises(ValidationError):
        parse_tool_input(MARKET_DATA, {"tickers": "NVDA"})
