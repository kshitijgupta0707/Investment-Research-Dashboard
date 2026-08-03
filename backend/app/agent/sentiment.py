"""Classifying news sentiment with the LLM.

The brief requires sentiment to come from the language model itself rather than
a separate classifier, so this reads each article's title and description and
labels it.

Two decisions shape the module:

* **Batched, not per-article.** Ten articles are one request, not ten. Per
  article it would be ten times the latency and ten times the fixed prompt
  cost, for a task the model handles in one pass.
* **Never fatal.** Sentiment enriches the news tool; it is not the news tool.
  If classification fails, the articles are returned unlabelled rather than
  the whole news result being lost.
"""

from __future__ import annotations

import logging

from google.genai import types
from pydantic import BaseModel

from app.agent.client import generate, translate_error
from app.schemas.news import Article, Sentiment

logger = logging.getLogger(__name__)

# Keeps one prompt bounded; longer batches are split.
BATCH_SIZE = 25
MAX_TOKENS = 2048

SYSTEM_PROMPT = """\
You classify financial news sentiment from the perspective of an investor \
holding the company's stock.

For each numbered article, decide whether the news is likely to be read as:

- positive: favourable for the company's prospects or valuation
- negative: unfavourable for them
- neutral: purely factual, mixed, or not really about the company's prospects

Judge the substance for that company, not the tone of the writing. A calmly \
worded report of falling revenue is negative. A dramatic headline about a \
competitor's troubles is not positive for this company unless it plainly \
benefits them.

Return one classification per article, using the index given.\
"""


class _ArticleSentiment(BaseModel):
    index: int
    sentiment: Sentiment


class _SentimentBatch(BaseModel):
    classifications: list[_ArticleSentiment]


def _prompt_for(articles: list[Article], ticker: str) -> str:
    lines = [f"Company: {ticker}", "", "Articles:"]
    for index, article in enumerate(articles):
        lines.append(f"[{index}] {article.title}")
        if article.description:
            lines.append(f"     {article.description}")
    return "\n".join(lines)


async def _classify_batch(articles: list[Article], ticker: str) -> dict[int, Sentiment]:
    """Label one batch. Raises on API failure; the caller degrades.

    Constrained decoding rather than a tool call: the output is a fixed shape
    with no branching, which `response_schema` expresses directly from the
    Pydantic model.
    """
    response = await generate(
        contents=_prompt_for(articles, ticker),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=_SentimentBatch,
            # No thinking_config: Gemini 3 models reject `thinking_budget=0`
            # with a bare 400, so thinking depth is left to the model. Cost is
            # bounded by batching instead -- one request per 25 articles.
        ),
        purpose="sentiment",
    )

    parsed = response.parsed
    if not isinstance(parsed, _SentimentBatch):
        raise ValueError("model returned no parsable classification")

    # Ignore indices the model invented; keep whatever lines up.
    return {
        item.index: item.sentiment
        for item in parsed.classifications
        if 0 <= item.index < len(articles)
    }


async def classify_articles(articles: list[Article], ticker: str) -> list[Article]:
    """Return the articles with `sentiment` filled in where possible.

    Always returns the same number of articles in the same order. On failure
    they come back unlabelled -- a report without sentiment badges is far
    better than no news at all.
    """
    if not articles:
        return articles

    labelled: list[Article] = []

    for start in range(0, len(articles), BATCH_SIZE):
        batch = articles[start : start + BATCH_SIZE]
        try:
            sentiments = await _classify_batch(batch, ticker)
        except Exception as exc:
            error = translate_error(exc)
            logger.warning(
                "sentiment classification failed; returning articles unlabelled",
                extra={"context": {"ticker": ticker, "articles": len(batch), "error": str(error)}},
            )
            labelled.extend(batch)
            continue

        labelled.extend(
            article.model_copy(update={"sentiment": sentiments.get(index)})
            for index, article in enumerate(batch)
        )

    unlabelled = sum(1 for a in labelled if a.sentiment is None)
    if unlabelled:
        logger.info(
            "some articles were left unlabelled",
            extra={"context": {"ticker": ticker, "unlabelled": unlabelled, "total": len(labelled)}},
        )
    return labelled
