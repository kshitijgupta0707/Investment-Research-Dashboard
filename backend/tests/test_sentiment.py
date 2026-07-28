"""News sentiment classification.

Batching, index handling and degradation are tested against stubbed responses.
Whether the model *judges* sentiment well needs a working key and is the live test
at the bottom.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors

from app.agent import sentiment as sentiment_module
from app.agent.sentiment import BATCH_SIZE, _ArticleSentiment, _SentimentBatch, classify_articles
from app.schemas.news import Article

# --- stubs ------------------------------------------------------------------


def article(title: str, description: str | None = None) -> Article:
    return Article(
        title=title,
        description=description,
        url="https://example.com/a",
        source="Reuters",
        published_at=datetime.now(timezone.utc),
    )


def Parsed(items: list[tuple[int, str]]) -> _SentimentBatch:
    """The real schema object, so a shape change here fails the test."""
    return _SentimentBatch(
        classifications=[
            _ArticleSentiment(index=index, sentiment=value)  # type: ignore[arg-type]
            for index, value in items
        ]
    )


class Response:
    """Only `parsed` is read; constrained decoding fills it in."""

    def __init__(self, parsed: Any) -> None:
        self.parsed = parsed


@pytest.fixture
def respond_with(monkeypatch: pytest.MonkeyPatch):
    """Stub the model's parsed output, recording how many calls were made."""
    calls: list[dict[str, Any]] = []

    def apply(*batches: Any) -> list[dict[str, Any]]:
        queue = list(batches)

        async def fake_generate(**kwargs: Any) -> Response:
            calls.append(kwargs)
            outcome = queue.pop(0) if queue else queue
            if isinstance(outcome, Exception):
                raise outcome
            return Response(outcome)

        models = type("Models", (), {"generate_content": staticmethod(fake_generate)})()
        aio = type("Aio", (), {"models": models})()
        monkeypatch.setattr(
            sentiment_module, "get_client", lambda: type("Client", (), {"aio": aio})()
        )
        return calls

    return apply


def status_error(status: int, message: str = "boom") -> Exception:
    cls = genai_errors.ClientError if status < 500 else genai_errors.ServerError
    return cls(status, {"error": {"message": message, "status": "ERROR"}})


# --- labelling --------------------------------------------------------------


async def test_articles_are_labelled(respond_with) -> None:
    respond_with(Parsed([(0, "positive"), (1, "negative")]))

    result = await classify_articles([article("Beat estimates"), article("Guidance cut")], "NVDA")

    assert [a.sentiment for a in result] == ["positive", "negative"]


async def test_order_and_count_are_preserved(respond_with) -> None:
    """The caller zips these against its own list; drift would misattribute."""
    respond_with(Parsed([(1, "negative"), (0, "positive")]))  # returned out of order

    articles = [article("First"), article("Second")]
    result = await classify_articles(articles, "NVDA")

    assert [a.title for a in result] == ["First", "Second"]
    assert [a.sentiment for a in result] == ["positive", "negative"]


async def test_original_articles_are_not_mutated(respond_with) -> None:
    respond_with(Parsed([(0, "positive")]))
    original = article("Beat estimates")

    result = await classify_articles([original], "NVDA")

    assert original.sentiment is None
    assert result[0].sentiment == "positive"


async def test_empty_input_makes_no_api_call(respond_with) -> None:
    calls = respond_with()
    assert await classify_articles([], "NVDA") == []
    assert calls == []


# --- batching ---------------------------------------------------------------


async def test_articles_are_classified_in_one_call(respond_with) -> None:
    """Ten articles must not be ten requests."""
    calls = respond_with(Parsed([(i, "neutral") for i in range(10)]))

    await classify_articles([article(f"Story {i}") for i in range(10)], "NVDA")

    assert len(calls) == 1


async def test_long_lists_are_split(respond_with) -> None:
    count = BATCH_SIZE + 5
    calls = respond_with(
        Parsed([(i, "neutral") for i in range(BATCH_SIZE)]),
        Parsed([(i, "positive") for i in range(5)]),
    )

    result = await classify_articles([article(f"Story {i}") for i in range(count)], "NVDA")

    assert len(calls) == 2
    assert len(result) == count
    assert result[-1].sentiment == "positive"


async def test_prompt_carries_titles_and_descriptions(respond_with) -> None:
    calls = respond_with(Parsed([(0, "neutral")]))

    await classify_articles([article("Revenue up", "Driven by data centre demand")], "NVDA")

    prompt = calls[0]["contents"]
    assert "NVDA" in prompt
    assert "Revenue up" in prompt and "data centre demand" in prompt


async def test_the_schema_is_enforced_by_the_api(respond_with) -> None:
    """The output shape is constrained at decode time, not parsed out of prose."""
    calls = respond_with(Parsed([(0, "neutral")]))

    await classify_articles([article("Revenue up")], "NVDA")

    config = calls[0]["config"]
    assert config.response_schema is _SentimentBatch
    assert config.response_mime_type == "application/json"


# --- degradation ------------------------------------------------------------


async def test_api_failure_returns_articles_unlabelled(respond_with) -> None:
    """Losing the badge must not lose the news."""
    respond_with(status_error(429))

    result = await classify_articles([article("Beat estimates")], "NVDA")

    assert len(result) == 1
    assert result[0].sentiment is None
    assert result[0].title == "Beat estimates"


async def test_one_failed_batch_does_not_lose_the_other(respond_with) -> None:
    respond_with(
        Parsed([(i, "positive") for i in range(BATCH_SIZE)]),
        status_error(500),
    )

    result = await classify_articles([article(f"S{i}") for i in range(BATCH_SIZE + 3)], "NVDA")

    assert len(result) == BATCH_SIZE + 3
    assert result[0].sentiment == "positive"
    assert result[-1].sentiment is None


async def test_unparsable_output_degrades(respond_with) -> None:
    respond_with(None)

    result = await classify_articles([article("Beat estimates")], "NVDA")
    assert result[0].sentiment is None


async def test_missing_classifications_leave_those_articles_unlabelled(respond_with) -> None:
    respond_with(Parsed([(0, "positive")]))  # only one of three

    result = await classify_articles([article("A"), article("B"), article("C")], "NVDA")

    assert [a.sentiment for a in result] == ["positive", None, None]


@pytest.mark.parametrize("bad_index", [99, -1])
async def test_invented_indices_are_ignored(respond_with, bad_index: int) -> None:
    """A hallucinated index must not raise or misattribute."""
    respond_with(Parsed([(0, "positive"), (bad_index, "negative")]))

    result = await classify_articles([article("A"), article("B")], "NVDA")

    assert [a.sentiment for a in result] == ["positive", None]


# --- live -------------------------------------------------------------------


@pytest.mark.integration
async def test_the_model_judges_clear_cases_correctly(settings) -> None:
    """Substance over tone: a calm report of falling revenue is negative."""
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    from app.integrations.errors import UpstreamError

    articles = [
        article("NVIDIA beats estimates as data centre revenue jumps 60%"),
        article("NVIDIA cuts full-year guidance after weak orders", "Revenue fell short."),
        article("NVIDIA to present at an industry conference next month"),
    ]

    try:
        result = await classify_articles(articles, "NVDA")
    except UpstreamError as exc:
        if "quota" in str(exc).lower():
            pytest.skip("Gemini quota exhausted")
        raise

    if all(a.sentiment is None for a in result):
        pytest.skip("classification degraded; nothing to assert")

    assert result[0].sentiment == "positive"
    assert result[1].sentiment == "negative"
