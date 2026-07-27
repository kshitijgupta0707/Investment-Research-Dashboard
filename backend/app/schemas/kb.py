"""Knowledge base chunks and search results."""

from __future__ import annotations

from pydantic import BaseModel


class KBChunk(BaseModel):
    """One indexed passage from a source document."""

    ticker: str
    doc_type: str
    chunk_text: str
    chunk_index: int
    source_label: str


class KBSearchHit(KBChunk):
    """A chunk with its relevance score for a particular query."""

    score: float


class KBSearchResult(BaseModel):
    query: str
    tickers: list[str] | None = None
    hits: list[KBSearchHit]
    source: str = "knowledge_base"
