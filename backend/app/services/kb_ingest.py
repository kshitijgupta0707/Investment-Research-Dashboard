"""Parsing and chunking of knowledge base source documents.

Source files carry a small header, then sections marked with `##`:

    ticker: NVDA
    company: NVIDIA Corporation
    doc_type: Form 10-K
    period: FY2025
    ---
    ## Item 1A. Risk Factors

    First paragraph...

Chunks are built from whole paragraphs and never span a section boundary, so
every excerpt the agent cites remains readable on its own and can be attributed
to a specific part of the document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas.kb import KBChunk

# Long enough to hold a claim with its context, short enough that a cited
# excerpt is quotable in a report.
TARGET_CHARS = 1200
MIN_CHARS = 120


@dataclass
class SourceDocument:
    ticker: str
    company: str
    doc_type: str
    period: str
    source_note: str
    sections: list[tuple[str, str]]


def parse_document(text: str) -> SourceDocument:
    """Split a source file into its header and `##` sections."""
    if "---" not in text:
        raise ValueError("document is missing the '---' header separator")

    raw_header, body = text.split("---", 1)

    header: dict[str, str] = {}
    for line in raw_header.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            header[key.strip()] = value.strip()

    for required in ("ticker", "doc_type"):
        if not header.get(required):
            raise ValueError(f"document header is missing '{required}'")

    sections: list[tuple[str, str]] = []
    for block in re.split(r"^##\s+", body, flags=re.MULTILINE)[1:]:
        title, _, content = block.partition("\n")
        if content.strip():
            sections.append((title.strip(), content.strip()))

    if not sections:
        raise ValueError("document has no '##' sections")

    return SourceDocument(
        ticker=header["ticker"].upper(),
        company=header.get("company", header["ticker"]),
        doc_type=header["doc_type"],
        period=header.get("period", ""),
        source_note=header.get("source_note", ""),
        sections=sections,
    )


def chunk_section(content: str) -> list[str]:
    """Group paragraphs into chunks of roughly TARGET_CHARS.

    Paragraphs are never split: a half-sentence excerpt is useless as a cited
    source. A paragraph longer than the target becomes its own chunk.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]

    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for paragraph in paragraphs:
        if current and size + len(paragraph) > TARGET_CHARS:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph)

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if len(c) >= MIN_CHARS]


def build_source_label(document: SourceDocument, section: str) -> str:
    """Attribution shown next to any claim drawn from this chunk.

    The corpus is synthetic, and the label says so: the application attributes
    every data point to a source, and an invented excerpt must not be
    presentable as a genuine regulatory filing.
    """
    parts = [document.ticker, document.period, document.doc_type]
    prefix = " ".join(p for p in parts if p)
    return f"{prefix} - {section} (illustrative sample)"


def chunk_document(text: str) -> list[KBChunk]:
    """Turn one source file into indexed chunks."""
    document = parse_document(text)

    chunks: list[KBChunk] = []
    for section, content in document.sections:
        for body in chunk_section(content):
            chunks.append(
                KBChunk(
                    ticker=document.ticker,
                    doc_type=document.doc_type,
                    chunk_text=body,
                    chunk_index=len(chunks),
                    source_label=build_source_label(document, section),
                )
            )
    return chunks


def load_corpus(directory: Path) -> dict[str, list[KBChunk]]:
    """Chunk every `.txt` document in `directory`, keyed by file name."""
    corpus: dict[str, list[KBChunk]] = {}
    for path in sorted(directory.glob("*.txt")):
        corpus[path.name] = chunk_document(path.read_text(encoding="utf-8"))
    return corpus
