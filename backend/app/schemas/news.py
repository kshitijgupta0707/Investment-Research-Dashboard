"""News articles.

Sentiment is deliberately absent here: NewsAPI does not provide it, and it is
classified by Claude from the title and description in a later step.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Article(BaseModel):
    title: str
    description: str | None = None
    url: str
    source: str
    published_at: datetime


class NewsResult(BaseModel):
    ticker: str
    query: str
    articles: list[Article]
    data_as_of: datetime
    source: str = "newsapi"
