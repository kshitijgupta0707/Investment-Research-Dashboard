"""The Turn-2 output contract.

This module is the only agreement between the backend and the frontend. The
frontend never parses prose: it switches on `Section.type` and renders the
matching component, so every shape a section can take is declared here.

Claude is asked for a deliberately loose JSON object and the strictness lives on
this side. A tool schema tight enough to express these shapes would be a nest of
`oneOf` branches that models follow unreliably, and a rejected response costs a
whole retry. Asking for something simple and validating it hard gets the same
guarantee at the frontend boundary for far fewer failed generations.

`partial`, `failed_tools` and `generated_at` are *not* supplied by the model.
The backend knows what actually failed; asking the model to self-report it
invites a confident lie about data it never received.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.news import Sentiment

Confidence = Literal["high", "medium", "low"]
SectionType = Literal["text", "table", "chart", "company_card", "sentiment"]
SourceType = Literal["api", "article", "filing"]


class Source(BaseModel):
    """Where one section's claims came from.

    Attribution is per section rather than per sentence: a sentence-level
    citation would need the model to track offsets it cannot reliably produce.
    """

    type: SourceType
    label: str
    url: str | None = None
    data_as_of: datetime | None = None


# --- section payloads -------------------------------------------------------


class TextContent(BaseModel):
    text: str


class TableContent(BaseModel):
    """A comparison grid. Ragged rows are padded rather than rejected."""

    columns: list[str]
    rows: list[list[str | float | int | None]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _pad_rows(self) -> TableContent:
        width = len(self.columns)
        self.rows = [(row + [None] * width)[:width] for row in self.rows]
        return self


class ChartPoint(BaseModel):
    date: date
    value: float


class ChartSeries(BaseModel):
    label: str
    points: list[ChartPoint] = Field(default_factory=list)


class ChartContent(BaseModel):
    series: list[ChartSeries] = Field(default_factory=list)
    y_label: str | None = None


class Metric(BaseModel):
    """One labelled figure on a company card, pre-formatted for display.

    `value` is a string because the model is asked to format it -- "$1.2T"
    reads better than 1200000000000.0 and the frontend should not be inventing
    unit conventions.
    """

    label: str
    value: str | None = None


class CompanyCardContent(BaseModel):
    ticker: str
    company_name: str | None = None
    metrics: list[Metric] = Field(default_factory=list)


class SentimentItem(BaseModel):
    headline: str
    sentiment: Sentiment
    ticker: str | None = None
    url: str | None = None


class SentimentContent(BaseModel):
    items: list[SentimentItem] = Field(default_factory=list)
    overall: Sentiment | None = None


SectionContent = (
    TextContent | TableContent | ChartContent | CompanyCardContent | SentimentContent
)

_CONTENT_MODELS: dict[str, type[BaseModel]] = {
    "text": TextContent,
    "table": TableContent,
    "chart": ChartContent,
    "company_card": CompanyCardContent,
    "sentiment": SentimentContent,
}


class Section(BaseModel):
    """One rendered block of the report.

    `content` is coerced to the model matching `type` before field validation,
    so a section is either fully typed or rejected -- the frontend never has to
    guess what it received.
    """

    title: str
    type: SectionType
    content: SectionContent
    confidence: Confidence
    sources: list[Source] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_content(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        model = _CONTENT_MODELS.get(data.get("type"))
        if model is None:
            return data

        content = data.get("content")
        # A text section is the one the model reliably returns as a bare string
        # instead of the wrapper object. Accepting both is cheaper than a retry.
        if model is TextContent and isinstance(content, str):
            return {**data, "content": TextContent(text=content)}
        if isinstance(content, dict):
            return {**data, "content": model.model_validate(content)}
        return data


class SynthesisOutput(BaseModel):
    """Exactly what Claude is asked to produce -- the prose, nothing else."""

    summary: str
    sections: list[Section] = Field(default_factory=list)


class ResearchReport(SynthesisOutput):
    """The full response the endpoint returns and a saved report stores.

    `partial` is true whenever *any* tool failed, which is broader than
    `ExecutionResult.partial` (some worked, some did not). A report built on
    nothing is degraded too, and the frontend banner should say so.
    """

    partial: bool = False
    failed_tools: list[str] = Field(default_factory=list)
    generated_at: datetime
