"""News articles.

NewsAPI does not supply sentiment. The LLM classifies it from the title and
description in a separate step, so `sentiment` is None until that runs -- and
stays None if it fails, since losing the label must not lose the article.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Sentiment = Literal["positive", "negative", "neutral"]


class Article(BaseModel):
    title: str
    description: str | None = None
    url: str
    source: str
    published_at: datetime
    sentiment: Sentiment | None = None


class NewsResult(BaseModel):
    ticker: str
    query: str
    articles: list[Article]
    data_as_of: datetime
    source: str = "newsapi"
