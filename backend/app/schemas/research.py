"""Request and response models for the research endpoint."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.research_queries import QueryStatus
from app.schemas.report import ResearchReport

# Long enough for a detailed multi-company comparison, short enough that a
# pasted document is rejected before it reaches a billable API call.
MAX_QUERY_CHARS = 2000


class ResearchQueryRequest(BaseModel):
    query_text: str = Field(
        min_length=3,
        max_length=MAX_QUERY_CHARS,
        description="The analyst's question, in plain language.",
        examples=["Compare NVIDIA and AMD on revenue growth, and flag the key risks."],
    )

    @field_validator("query_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Whitespace is not a question.

        `min_length` alone would accept "   ", which reaches Claude as an empty
        prompt and comes back as a confused report rather than a 400.
        """
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("query_text must contain at least 3 non-whitespace characters")
        return stripped


class ResearchQueryResponse(BaseModel):
    """The report plus what it took to produce it.

    `report` is the contract the frontend renders. The rest is provenance: which
    tools ran, whether anything degraded, and the history id, so the UI can link
    a result to its entry without a second round trip.
    """

    query_id: UUID
    query_text: str
    tools_selected: list[str]
    status: QueryStatus
    latency_ms: float
    report: ResearchReport
