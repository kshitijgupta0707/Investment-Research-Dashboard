import "server-only";

import { apiFetch } from "@/lib/api/client";
import type {
  Organization,
  Page,
  QueryHistoryEntry,
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

export function getWatchlist(): Promise<WatchlistEntry[]> {
  return authorized<WatchlistEntry[]>("/api/watchlist");
}

export function getOrganization(): Promise<Organization> {
  return authorized<Organization>("/api/org");
}
