import "server-only";

import { apiFetch } from "@/lib/api/client";
import type {
  Invite,
  Member,
  Organization,
  Page,
  QueryHistoryEntry,
  ReportDetail,
  ReportSummary,
  WatchlistEntry,
} from "@/lib/api/types";
import { getAccessToken } from "@/lib/supabase/server";

/**
 * Typed reads for the signed-in user's data.
 *
 * `server-only` makes importing this from a client component a build error
 * rather than a runtime surprise: these attach the access token, which has no
 * business in the browser bundle.
 *
 * Each function throws `ApiError` on failure. Callers render inside their own
 * Suspense and error boundaries, so one endpoint being down degrades a single
 * widget instead of the page.
 */

async function authorized<T>(path: string): Promise<T> {
  const token = await getAccessToken();
  return apiFetch<T>(path, { token });
}

export function getRecentQueries(limit = 5): Promise<Page<QueryHistoryEntry>> {
  return authorized<Page<QueryHistoryEntry>>(`/api/queries?limit=${limit}`);
}

export function getRecentReports(limit = 5): Promise<Page<ReportSummary>> {
  return authorized<Page<ReportSummary>>(`/api/reports?limit=${limit}`);
}

export interface ReportQuery {
  /** Full-text search over the query text. */
  q?: string;
  /** Exact tag match, case-insensitive. */
  tag?: string;
  limit?: number;
  offset?: number;
}

export function listReports(params: ReportQuery = {}): Promise<Page<ReportSummary>> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.tag) search.set("tag", params.tag);
  search.set("limit", String(params.limit ?? REPORTS_PER_PAGE));
  search.set("offset", String(params.offset ?? 0));

  return authorized<Page<ReportSummary>>(`/api/reports?${search}`);
}

export function getReport(id: string): Promise<ReportDetail> {
  return authorized<ReportDetail>(`/api/reports/${id}`);
}

export const REPORTS_PER_PAGE = 20;

export function getWatchlist(): Promise<WatchlistEntry[]> {
  return authorized<WatchlistEntry[]>("/api/watchlist");
}

export function getOrganization(): Promise<Organization> {
  return authorized<Organization>("/api/org");
}

/** Admin-only. The API answers 403 for anyone else. */
export function getMembers(): Promise<Member[]> {
  return authorized<Member[]>("/api/org/members");
}

/** Admin-only. */
export function getInvites(): Promise<Invite[]> {
  return authorized<Invite[]>("/api/org/invites");
}
