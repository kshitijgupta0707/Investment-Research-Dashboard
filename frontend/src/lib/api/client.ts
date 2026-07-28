import { env } from "@/lib/env";

import { ApiError } from "./errors";
import type { Envelope } from "./types";

interface RequestOptions {
  /** Supabase access token, sent as `Authorization: Bearer`. */
  token?: string | null;
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Next.js fetch cache hint. Defaults to no-store: this data is per-user. */
  cache?: RequestCache;
  signal?: AbortSignal;
}

/**
 * The single door to the backend.
 *
 * Unwraps the response envelope so callers receive `data` directly, and turns
 * any non-success into a thrown `ApiError`. Nothing else in the app calls
 * `fetch` against the API, so the token header, the envelope shape and the
 * error taxonomy are each defined exactly once.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, method = "GET", body, cache = "no-store", signal } = options;

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method,
    cache,
    signal,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // A crash before the exception handler, or a proxy in the way, can return
  // something that is not our envelope. Treat that as an error rather than
  // letting `undefined` propagate as data.
  let envelope: Envelope<T> | null = null;
  try {
    envelope = (await response.json()) as Envelope<T>;
  } catch {
    envelope = null;
  }

  const requestId = envelope?.meta?.request_id ?? null;

  if (!response.ok || !envelope?.success) {
    throw new ApiError(response.status, envelope?.error ?? null, requestId);
  }

  return envelope.data as T;
}
