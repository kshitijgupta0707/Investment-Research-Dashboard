import type { ResearchQueryResponse } from "@/lib/api/types";

/** Mirrors `MAX_QUERY_CHARS` in backend/app/schemas/research.py. */
export const MAX_QUERY_CHARS = 2000;
export const MIN_QUERY_CHARS = 3;

/** Warn as the limit approaches rather than only on rejection. */
export const QUERY_WARN_AT = MAX_QUERY_CHARS - 200;

export type ResearchState =
  | { status: "idle" }
  | { status: "error"; message: string; queryText: string }
  | { status: "done"; result: ResearchQueryResponse; queryText: string };

export const idleResearchState: ResearchState = { status: "idle" };

export type SaveState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "saved"; reportId: string };

export const idleSaveState: SaveState = { status: "idle" };

/**
 * Example questions, shown on an empty page.
 *
 * Chosen from the acceptance table in PROJECT_PLAN §7 so that clicking through
 * them demonstrates the point: the first calls one tool, the last calls three,
 * and the model decides which -- nothing here routes on keywords.
 */
export const EXAMPLE_QUERIES: readonly string[] = [
  "What's the latest news on Tesla?",
  "What's NVIDIA's current P/E and market cap?",
  "Analyze NVIDIA's Q3 earnings, compare revenue growth with AMD and Intel, and give a risk assessment.",
  "What is a P/E ratio?",
];
