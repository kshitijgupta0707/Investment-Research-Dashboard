"""Request and response models for saved reports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.report import ResearchReport
from app.schemas.research import MAX_QUERY_CHARS

MAX_TAGS = 10
MAX_TAG_CHARS = 32

# Long enough for a considered desk view, short enough that the note stays a
# note rather than becoming a second report.
MAX_NOTES_CHARS = 4000


def _clean_tags(value: list[str]) -> list[str]:
    """Lowercase, trim, drop blanks, de-duplicate, preserve order.

    Normalising on the way in is what makes filtering exact rather than fuzzy:
    the query can use the GIN index directly instead of lowering every row's
    array at read time.
    """
    seen: dict[str, None] = {}
    for raw in value:
        tag = raw.strip().lower()
        if not tag:
            continue
        if len(tag) > MAX_TAG_CHARS:
            raise ValueError(f"tags must be {MAX_TAG_CHARS} characters or fewer")
        seen.setdefault(tag, None)

    if len(seen) > MAX_TAGS:
        raise ValueError(f"a report may have at most {MAX_TAGS} tags")
    return list(seen)


class ReportCreate(BaseModel):
    """Saving a result produced by `POST /api/research/query`.

    `structured_result` is validated against the full Turn-2 contract rather
    than accepted as free-form JSON. Anything stored here will later be handed
    straight back to the renderer, so a malformed report must be rejected at
    write time -- not discovered when someone opens it a week later.
    """

    query_text: str = Field(min_length=3, max_length=MAX_QUERY_CHARS)
    structured_result: ResearchReport
    tags: list[str] = Field(default_factory=list)

    @field_validator("query_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("query_text must contain at least 3 non-whitespace characters")
        return stripped

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)


class ReportTagsUpdate(BaseModel):
    """Tags are the only mutable field.

    The query text and the result are a record of what was asked and what came
    back; editing either would make a saved report a claim about data that was
    never retrieved. Re-running the query produces a new report instead.
    """

    tags: list[str]

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)


class ReportNotesUpdate(BaseModel):
    """An analyst's own commentary, kept beside the agent's output.

    This never touches `structured_result`. A saved report is the record of what
    the agent retrieved, and every source tag rendered in the UI rests on that
    being true -- so a human's words go in their own field, attributed to them,
    rather than being woven into sections that claim a provider as their source.

    Sending null, or only whitespace, clears the note.
    """

    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)

    @field_validator("notes")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        # An empty string and "no note" are the same state; storing both would
        # give the UI two cases to distinguish for no reason.
        return stripped or None


class ReportSummary(BaseModel):
    """A list row. Deliberately without `structured_result`.

    A full report is tens of kilobytes; twenty of them would make the list
    endpoint slower than the query that produced them.
    """

    id: UUID
    query_text: str
    tags: list[str]
    created_by: UUID
    created_by_email: str
    created_at: datetime
    updated_at: datetime
    # Whether a note exists, not the note itself -- enough for the list to badge
    # an annotated report without carrying every note's text.
    has_notes: bool = False


class ReportDetail(ReportSummary):
    structured_result: ResearchReport
    analyst_notes: str | None = None
    notes_updated_at: datetime | None = None
    notes_updated_by_email: str | None = None


class ReportPage(BaseModel):
    """`total` is the count before pagination, so the UI can show a page count."""

    items: list[ReportSummary]
    total: int
    limit: int
    offset: int
