"""BM25 keyword search over the seeded filing corpus.

This is the agent's third tool. The index is held in memory and built from
`kb_documents`, which is the durable store -- rebuilding it is cheap because
the corpus is a few hundred chunks, and keeping the source of truth in Postgres
means a redeploy cannot lose it.

BM25 rather than embeddings: the brief accepts keyword search, it needs no
model or vector store, and results are explainable -- a reviewer can see which
terms matched.
"""

from __future__ import annotations

import asyncio
import logging
import re

import asyncpg
from rank_bm25 import BM25Okapi

from app.schemas.kb import KBChunk, KBSearchHit, KBSearchResult

logger = logging.getLogger(__name__)

# Common English plus filing boilerplate that appears in nearly every chunk and
# therefore separates nothing.
STOPWORDS = frozenset(
    """
    a an and are as at be been but by for from has have in into is it its of on
    or that the their there these this to was were which with would could may
    might will shall can company companys other such any all more most been
    during including under over than then them they we our us if not no
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9]+")


def _stem(token: str) -> str:
    """Crude plural stripping.

    Not linguistically correct -- "analysis" becomes "analysi" -- but it is
    applied identically to queries and documents, so consistency is what
    matters, not correctness. Without it, "capital ratios" fails to match
    "capital ratio" and "key risks" fails to match "risk factors".

    Words ending in "ss" or "us" are left alone, so "gross" and "business"
    survive intact.
    """
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, strip plurals.

    Numbers are kept: "2025" and "10" carry meaning in filings.
    """
    # Stem first, then filter: otherwise "companies" stems to "company" and
    # survives, while a literal "company" is dropped, and the two stop matching.
    stemmed = (_stem(t) for t in _TOKEN.findall(text.lower()))
    return [t for t in stemmed if len(t) > 1 and t not in STOPWORDS]


class KnowledgeBaseIndex:
    """An immutable BM25 index over a set of chunks."""

    def __init__(self, chunks: list[KBChunk]) -> None:
        self.chunks = chunks
        # The source label carries the section heading ("Item 1A. Risk
        # Factors", "Balance Sheet and Capital"), which is a strong relevance
        # signal that the body text alone often does not restate.
        corpus = [tokenize(f"{c.source_label} {c.chunk_text}") for c in chunks]
        self._bm25 = BM25Okapi(corpus) if chunks else None

    def __len__(self) -> int:
        return len(self.chunks)

    @property
    def tickers(self) -> set[str]:
        return {c.ticker for c in self.chunks}

    def search(
        self,
        query: str,
        tickers: list[str] | None = None,
        limit: int = 5,
        relative_floor: float = 0.25,
    ) -> list[KBSearchHit]:
        """Rank chunks against `query`, optionally restricted to tickers.

        Scoring runs over the whole corpus before filtering, so term rarity is
        judged against every document rather than only the selected companies.

        The cutoff is **relative to the best hit**, not an absolute number.
        BM25 scores are not comparable across queries: a precise query
        ("capital ratios and deposits") peaks above 8, while a broad one ("key
        risks") peaks below 1 because its terms appear almost everywhere. A
        fixed floor would silently return nothing for the broad query, which
        looks like a broken tool rather than a low-signal question.

        A query whose every term is absent still scores zero throughout and
        correctly returns nothing.
        """
        if self._bm25 is None:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        wanted = {t.upper() for t in tickers} if tickers else None
        scores = self._bm25.get_scores(tokens)

        candidates = [
            (chunk, float(score))
            for chunk, score in zip(self.chunks, scores, strict=True)
            if score > 0 and (wanted is None or chunk.ticker in wanted)
        ]
        if not candidates:
            return []

        cutoff = max(score for _, score in candidates) * relative_floor
        hits = [
            KBSearchHit(**chunk.model_dump(), score=score)
            for chunk, score in candidates
            if score >= cutoff
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]


# --- loading ----------------------------------------------------------------

_index: KnowledgeBaseIndex | None = None
_lock = asyncio.Lock()


async def fetch_chunks(pool: asyncpg.Pool) -> list[KBChunk]:
    rows = await pool.fetch(
        """
        select ticker, doc_type, chunk_text, chunk_index, source_label
        from kb_documents
        order by ticker, chunk_index
        """
    )
    return [KBChunk(**dict(row)) for row in rows]


async def get_index(pool: asyncpg.Pool, *, reload: bool = False) -> KnowledgeBaseIndex:
    """Return the cached index, building it on first use.

    The lock prevents concurrent first requests each building their own copy.
    """
    global _index
    if _index is not None and not reload:
        return _index

    async with _lock:
        if _index is None or reload:
            chunks = await fetch_chunks(pool)
            _index = KnowledgeBaseIndex(chunks)
            logger.info(
                "knowledge base index built",
                extra={"context": {"chunks": len(chunks), "tickers": sorted(_index.tickers)}},
            )
    return _index


def reset_index() -> None:
    """Drop the cached index. Used after ingestion and by tests."""
    global _index
    _index = None


async def search_knowledge_base(
    pool: asyncpg.Pool,
    query: str,
    tickers: list[str] | None = None,
    limit: int = 5,
) -> KBSearchResult:
    index = await get_index(pool)
    return KBSearchResult(
        query=query,
        tickers=[t.upper() for t in tickers] if tickers else None,
        hits=index.search(query, tickers=tickers, limit=limit),
    )
