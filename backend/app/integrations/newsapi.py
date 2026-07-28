"""Recent news per company, via NewsAPI.

Sentiment is not requested here -- NewsAPI does not supply it, and the LLM
classifies it from the title and description in a later step.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.integrations.errors import (
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.schemas.news import Article, NewsResult
from app.utils.config import get_settings

logger = logging.getLogger(__name__)

# The free tier only serves the last month.
MAX_DAYS = 28
DEFAULT_LIMIT = 10


class NewsAPIClient:
    name = "newsapi"
    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.newsapi_api_key
        self._timeout = timeout or settings.upstream_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def build_query(ticker: str, company_name: str | None = None) -> str:
        """Bias towards finance coverage of the company.

        A bare ticker is far too loose -- searching "NVIDIA" alone surfaces
        laptop deals. Requiring the term in the title, and pairing it with a
        finance word, filters most of that out.
        """
        subject = f'"{company_name}"' if company_name else ticker
        return f"{subject} AND (stock OR shares OR earnings OR revenue OR market)"

    async def get_news(
        self,
        ticker: str,
        company_name: str | None = None,
        days: int = 30,
        limit: int = DEFAULT_LIMIT,
    ) -> NewsResult:
        if not self.configured:
            raise UpstreamUnavailable(self.name, "NEWSAPI_API_KEY is not set")

        window = min(days, MAX_DAYS)
        query = self.build_query(ticker, company_name)
        params = {
            "q": query,
            "from": (datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat(),
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": str(min(limit, 100)),
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    self.BASE_URL, params=params, headers={"X-Api-Key": self._api_key}
                )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout(self.name, f"no response within {self._timeout}s") from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(self.name, str(exc)) from exc

        if response.status_code == 429:
            raise UpstreamRateLimited(self.name, "request quota exhausted")
        if response.status_code == 401:
            raise UpstreamUnavailable(self.name, "API key rejected")
        if response.status_code >= 400:
            raise UpstreamUnavailable(self.name, f"HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamUnavailable(self.name, "response was not JSON") from exc

        if payload.get("status") != "ok":
            raise UpstreamUnavailable(self.name, str(payload.get("message", "request rejected")))

        return NewsResult(
            ticker=ticker.upper(),
            query=query,
            articles=[a for a in map(self._to_article, payload.get("articles", [])) if a],
            data_as_of=datetime.now(timezone.utc),
        )

    @staticmethod
    def _to_article(raw: dict) -> Article | None:
        """Skip unusable entries rather than failing the whole batch.

        NewsAPI returns "[Removed]" placeholders for retracted articles.
        """
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        published = raw.get("publishedAt")
        if not title or not url or not published or title == "[Removed]":
            return None

        try:
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            return None

        return Article(
            title=title,
            description=(raw.get("description") or None),
            url=url,
            source=(raw.get("source") or {}).get("name") or "unknown",
            published_at=published_at,
        )
