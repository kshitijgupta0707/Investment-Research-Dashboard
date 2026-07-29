"use server";

import { apiFetch } from "@/lib/api/client";
import { messageFor } from "@/lib/api/errors";
import type { ReportSummary, ResearchQueryResponse } from "@/lib/api/types";
import { getAccessToken } from "@/lib/supabase/server";

import { MAX_QUERY_CHARS, MIN_QUERY_CHARS, type ResearchState, type SaveState } from "./schema";

/**
 * Run one research query.
 *
 * A server action rather than a client `fetch` so the access token never
 * reaches the browser. The call is slow by nature -- two model turns with tool
 * execution in between -- and the form's pending state covers that wait.
 *
 * Failures come back as state rather than thrown, because every one of them is
 * something the analyst can act on: retry, shorten the question, or wait out a
 * rate limit.
 */
export async function runQuery(_previous: ResearchState, formData: FormData): Promise<ResearchState> {
  const queryText = String(formData.get("query_text") ?? "").trim();

  if (queryText.length < MIN_QUERY_CHARS) {
    return { status: "error", message: "Ask a question first.", queryText };
  }
  if (queryText.length > MAX_QUERY_CHARS) {
    return {
      status: "error",
      message: `That question is ${queryText.length} characters; the limit is ${MAX_QUERY_CHARS}.`,
      queryText,
    };
  }

  try {
    const result = await apiFetch<ResearchQueryResponse>("/api/research/query", {
      token: await getAccessToken(),
      method: "POST",
      body: { query_text: queryText },
    });

    // No `revalidatePath`: it re-renders the route tree, which resets the
    // `useFormState` holding this result. Reads are `no-store` anyway.
    return { status: "done", result, queryText };
  } catch (error) {
    return { status: "error", message: messageFor(error), queryText };
  }
}

/**
 * Persist a result as a saved report.
 *
 * The full structured result is sent back verbatim rather than referenced by
 * query id: a report is a frozen snapshot of what was returned, and re-running
 * the query to rebuild it would produce different figures.
 */
export async function saveReport(_previous: SaveState, formData: FormData): Promise<SaveState> {
  const payload = String(formData.get("payload") ?? "");
  const queryText = String(formData.get("query_text") ?? "");
  const tags = String(formData.get("tags") ?? "")
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);

  if (!payload) return { status: "error", message: "There is no result to save." };

  try {
    const saved = await apiFetch<ReportSummary>("/api/reports", {
      token: await getAccessToken(),
      method: "POST",
      body: { query_text: queryText, structured_result: JSON.parse(payload), tags },
    });

    // No `revalidatePath`, same reason as `runQuery`.
    return { status: "saved", reportId: saved.id };
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }
}
