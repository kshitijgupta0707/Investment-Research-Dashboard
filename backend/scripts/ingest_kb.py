"""Chunk the knowledge base source documents and load them into Postgres.

Usage:
    python backend/scripts/ingest_kb.py            # replace the corpus
    python backend/scripts/ingest_kb.py --dry-run  # report chunking only

Re-running is safe: rows for each ticker present in the source directory are
replaced, so the table always matches the files on disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.kb_ingest import load_corpus  # noqa: E402
from app.utils.config import get_settings  # noqa: E402

CORPUS_DIR = BACKEND_ROOT / "data" / "kb"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chunk and report without writing")
    args = parser.parse_args()

    if not CORPUS_DIR.is_dir():
        print(f"No corpus directory at {CORPUS_DIR}")
        return 1

    corpus = load_corpus(CORPUS_DIR)
    if not corpus:
        print(f"No .txt documents found in {CORPUS_DIR}")
        return 1

    total = 0
    for filename, chunks in corpus.items():
        ticker = chunks[0].ticker if chunks else "?"
        longest = max((len(c.chunk_text) for c in chunks), default=0)
        print(f"  {filename:<16} {ticker:<5} {len(chunks):>3} chunks  (longest {longest} chars)")
        total += len(chunks)

    print(f"\n{total} chunks from {len(corpus)} documents")

    if args.dry_run:
        return 0

    database_url = get_settings().database_url
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    tickers = sorted({c.ticker for chunks in corpus.values() for c in chunks})

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from kb_documents where ticker = any(%s)", (tickers,))
            removed = cur.rowcount

            cur.executemany(
                """
                insert into kb_documents (ticker, doc_type, chunk_text, chunk_index, source_label)
                values (%s, %s, %s, %s, %s)
                """,
                [
                    (c.ticker, c.doc_type, c.chunk_text, c.chunk_index, c.source_label)
                    for chunks in corpus.values()
                    for c in chunks
                ],
            )
        conn.commit()

    print(f"Replaced {removed} existing row(s); inserted {total} for {', '.join(tickers)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
