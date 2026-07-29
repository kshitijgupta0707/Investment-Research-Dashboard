"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api/client";
import { messageFor } from "@/lib/api/errors";
import type { ReportDetail } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { getAccessToken } from "@/lib/supabase/server";

import {
  MAX_NOTES_CHARS,
  MAX_TAGS,
  MAX_TAG_CHARS,
  type NotesState,
  type TagsState,
} from "./schema";

/**
 * Replace a report's tags.
 *
 * Tags are the only mutable field: the query text and the result are a record
 * of what was asked and what came back, and editing either would make a saved
 * report a claim about data that was never retrieved. Re-running produces a new
 * report instead.
 *
 * Authorisation is the backend's -- it answers 403 unless the caller created
 * the report or is an admin, whatever this form chose to render.
 */
export async function updateTags(_previous: TagsState, formData: FormData): Promise<TagsState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { status: "error", message: "Missing report id." };

  const tags = normaliseTags(String(formData.get("tags") ?? ""));

  if (tags.length > MAX_TAGS) {
    return { status: "error", message: `A report may have at most ${MAX_TAGS} tags.` };
  }
  const overlong = tags.find((tag) => tag.length > MAX_TAG_CHARS);
  if (overlong) {
    return {
      status: "error",
      message: `"${overlong}" is too long — tags are ${MAX_TAG_CHARS} characters or fewer.`,
    };
  }

  try {
    await apiFetch<ReportDetail>(`/api/reports/${id}`, {
      token: await getAccessToken(),
      method: "PATCH",
      body: { tags },
    });
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }

  revalidatePath(`${routes.reports}/${id}`);
  revalidatePath(routes.reports);
  revalidatePath(routes.dashboard);

  return { status: "saved", tags };
}

/** Save an analyst's commentary. An empty box clears the note. */
export async function updateNotes(
  _previous: NotesState,
  formData: FormData,
): Promise<NotesState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { status: "error", message: "Missing report id." };

  const raw = String(formData.get("notes") ?? "").trim();

  if (raw.length > MAX_NOTES_CHARS) {
    return {
      status: "error",
      message: `That note is ${raw.length} characters; the limit is ${MAX_NOTES_CHARS}.`,
    };
  }

  try {
    await apiFetch<ReportDetail>(`/api/reports/${id}/notes`, {
      token: await getAccessToken(),
      method: "PATCH",
      body: { notes: raw || null },
    });
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }

  revalidatePath(`${routes.reports}/${id}`);
  revalidatePath(routes.reports);

  return { status: "saved", cleared: raw.length === 0 };
}

/**
 * Delete a report.
 *
 * Redirects to the list on success; there is nothing left to render at the
 * detail URL. A failure returns state so the reason stays on screen.
 */
export async function deleteReport(
  _previous: TagsState,
  formData: FormData,
): Promise<TagsState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { status: "error", message: "Missing report id." };

  try {
    await apiFetch<{ id: string }>(`/api/reports/${id}`, {
      token: await getAccessToken(),
      method: "DELETE",
    });
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }

  revalidatePath(routes.reports);
  revalidatePath(routes.dashboard);
  redirect(routes.reports);
}

/**
 * Lower-case, trim, drop blanks, de-duplicate, preserve order.
 *
 * Matches the backend's own normalisation so what the user typed and what the
 * tag filter later matches are the same string.
 */
function normaliseTags(raw: string): string[] {
  const seen = new Set<string>();
  for (const part of raw.split(",")) {
    const tag = part.trim().toLowerCase();
    if (tag) seen.add(tag);
  }
  return Array.from(seen);
}
