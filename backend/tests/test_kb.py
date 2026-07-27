"""Knowledge base chunking, indexing and search."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.integrations.kb_search import (
    KnowledgeBaseIndex,
    fetch_chunks,
    reset_index,
    search_knowledge_base,
    tokenize,
)
from app.schemas.kb import KBChunk
from app.services.kb_ingest import (
    build_source_label,
    chunk_document,
    chunk_section,
    load_corpus,
    parse_document,
)

CORPUS_DIR = Path(__file__).resolve().parents[1] / "data" / "kb"

DOCUMENT = """ticker: TEST
company: Test Corporation
doc_type: Form 10-K
period: FY2025
source_note: ILLUSTRATIVE SAMPLE
---
## Item 1. Business

The company sells widgets to industrial customers across several regions and
maintains a modest research programme.

## Item 1A. Risk Factors

Supply concentration with a single foundry presents material manufacturing
risk to the company should capacity become constrained.

Regulatory change could restrict sales into certain markets and reduce the
addressable demand available to the company.
"""


# --- parsing ----------------------------------------------------------------


def test_header_and_sections_are_parsed() -> None:
    document = parse_document(DOCUMENT)
    assert document.ticker == "TEST"
    assert document.doc_type == "Form 10-K"
    assert [title for title, _ in document.sections] == ["Item 1. Business", "Item 1A. Risk Factors"]


def test_ticker_is_uppercased() -> None:
    assert parse_document(DOCUMENT.replace("ticker: TEST", "ticker: test")).ticker == "TEST"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("ticker: X\ndoc_type: Y\n## Section\nbody", "no header separator"),
        ("doc_type: Y\n---\n## Section\nbody", "no ticker"),
        ("ticker: X\ndoc_type: Y\n---\njust prose", "no sections"),
    ],
)
def test_malformed_documents_are_rejected(text: str, reason: str) -> None:
    """Ingestion should fail loudly rather than index a half-parsed file."""
    with pytest.raises(ValueError):
        parse_document(text)


# --- chunking ---------------------------------------------------------------


def test_paragraphs_are_never_split() -> None:
    """A half-sentence excerpt is useless as a cited source."""
    paragraph = "word " * 120
    chunks = chunk_section(f"{paragraph.strip()}\n\n{paragraph.strip()}")
    for chunk in chunks:
        assert chunk.count("word") % 120 == 0


def test_short_paragraphs_are_grouped() -> None:
    body = "\n\n".join(["This is a reasonably long sentence about the business." * 3] * 2)
    assert len(chunk_section(body)) == 1


def test_trivial_fragments_are_dropped() -> None:
    assert chunk_section("too short") == []


def test_chunk_indexes_are_sequential() -> None:
    chunks = chunk_document(DOCUMENT)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.ticker == "TEST" for c in chunks)


def test_source_label_marks_the_corpus_as_synthetic() -> None:
    """The app attributes every data point; invented text must say so."""
    document = parse_document(DOCUMENT)
    label = build_source_label(document, "Item 1A. Risk Factors")
    assert "illustrative sample" in label
    assert "TEST" in label and "Item 1A. Risk Factors" in label


# --- tokenizing -------------------------------------------------------------


def test_stopwords_are_removed() -> None:
    assert "the" not in tokenize("the company and the market")


def test_numbers_are_kept() -> None:
    assert "2025" in tokenize("fiscal year 2025 results")


@pytest.mark.parametrize(
    ("plural", "singular"),
    [("risks", "risk"), ("ratios", "ratio"), ("deposits", "deposit"), ("facilities", "facility")],
)
def test_plurals_match_singulars(plural: str, singular: str) -> None:
    """Without this, 'capital ratios' misses 'capital ratio'."""
    assert tokenize(plural) == tokenize(singular) != []


def test_stemming_happens_before_stopword_removal() -> None:
    """Otherwise a plural stems into a stopword and outlives its singular."""
    assert tokenize("companies") == tokenize("company") == []


@pytest.mark.parametrize("word", ["gross", "business", "analysis"])
def test_double_s_and_similar_endings_survive(word: str) -> None:
    assert tokenize(word) == [word]


# --- search -----------------------------------------------------------------


def index_of(*rows: tuple[str, str, str]) -> KnowledgeBaseIndex:
    return KnowledgeBaseIndex(
        [
            KBChunk(
                ticker=ticker,
                doc_type="Form 10-K",
                chunk_text=text,
                chunk_index=i,
                source_label=label,
            )
            for i, (ticker, label, text) in enumerate(rows)
        ]
    )


@pytest.fixture
def index() -> KnowledgeBaseIndex:
    return index_of(
        ("NVDA", "NVDA - Item 1A. Risk Factors", "Manufacturing is concentrated with foundries in Taiwan and supply may be constrained."),
        ("NVDA", "NVDA - Competitive Landscape", "The company competes with custom accelerators designed by cloud customers."),
        ("AMD", "AMD - Item 1A. Risk Factors", "The company competes against a larger rival whose software ecosystem is mature."),
        ("JPM", "JPM - Item 7. Balance Sheet and Capital", "Total deposits were approximately 2.4 trillion dollars and the capital ratio was 15 percent."),
    )


def test_search_ranks_the_relevant_chunk_first(index: KnowledgeBaseIndex) -> None:
    hits = index.search("foundry manufacturing concentration in Taiwan")
    assert hits and "Taiwan" in hits[0].chunk_text


def test_section_heading_is_searchable(index: KnowledgeBaseIndex) -> None:
    """Body text often never restates its own section title."""
    hits = index.search("balance sheet capital ratios")
    assert hits and hits[0].ticker == "JPM"


def test_ticker_filter_restricts_results(index: KnowledgeBaseIndex) -> None:
    hits = index.search("software ecosystem maturity", tickers=["AMD"])
    assert hits and all(h.ticker == "AMD" for h in hits)


def test_ticker_filter_is_case_insensitive(index: KnowledgeBaseIndex) -> None:
    assert index.search("software ecosystem maturity", tickers=["amd"])


def test_limit_is_respected(index: KnowledgeBaseIndex) -> None:
    assert len(index.search("capital deposits foundry software", limit=1)) <= 1


def test_terms_common_to_half_the_corpus_carry_no_signal(index: KnowledgeBaseIndex) -> None:
    """Standard BM25: a term in >=50% of documents has zero IDF.

    "competes" appears in half these chunks, so it discriminates nothing and
    the score floor drops it. Harmless on the real corpus, where such terms are
    either rare or already stopwords -- but worth knowing when debugging.
    """
    assert index.search("competes") == []


def test_query_of_only_stopwords_returns_nothing(index: KnowledgeBaseIndex) -> None:
    assert index.search("the and of") == []


def test_irrelevant_query_returns_nothing(index: KnowledgeBaseIndex) -> None:
    """A score floor keeps unrelated excerpts out of a report."""
    assert index.search("photosynthesis chlorophyll") == []


def test_empty_index_is_safe() -> None:
    assert KnowledgeBaseIndex([]).search("anything") == []


# --- the real corpus --------------------------------------------------------


def test_shipped_corpus_chunks_cleanly() -> None:
    corpus = load_corpus(CORPUS_DIR)
    assert len(corpus) >= 5, "expected at least five source documents"

    chunks = [c for chunks in corpus.values() for c in chunks]
    assert all(c.chunk_text.strip() for c in chunks)
    assert all("illustrative sample" in c.source_label for c in chunks)

    tickers = {c.ticker for c in chunks}
    assert {"NVDA", "AMD", "INTC"} <= tickers, "acceptance queries compare these three"
    assert {"JPM", "GS", "MS"} <= tickers, "acceptance queries compare these three banks"


@pytest.mark.integration
async def test_search_against_the_ingested_corpus(requires_db) -> None:
    from app import db

    pool = await db.connect()
    reset_index()
    try:
        if not await fetch_chunks(pool):
            pytest.skip("kb_documents is empty; run scripts/ingest_kb.py")

        result = await search_knowledge_base(
            pool, "balance sheet capital ratios and deposits", tickers=["JPM", "GS", "MS"], limit=3
        )
        assert result.hits
        assert "Balance Sheet" in result.hits[0].source_label
        assert result.hits[0].ticker in {"JPM", "GS", "MS"}
    finally:
        reset_index()
        await db.disconnect()
