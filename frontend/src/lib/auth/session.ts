import { cache } from "react";

import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { CurrentUser } from "@/lib/api/types";
import { getAccessToken } from "@/lib/supabase/server";

/**
 * Three distinct states, kept distinct.
 *
 * Collapsing `unprovisioned` into `anonymous` is what caused a redirect loop:
 * the layout sent them to /login, middleware saw a valid session and sent them
 * straight back. They need different handling, so they get different types.
 */
export type SessionState =
  | { status: "anonymous" }
  | { status: "unprovisioned" }
  | { status: "member"; user: CurrentUser };

/**
 * Resolve who is signed in, according to the backend.
 *
 * The role is deliberately read from Postgres rather than the JWT, so an admin
 * demoted mid-session loses admin on their next request rather than whenever
 * their token happens to expire.
 *
 * Wrapped in `cache` so a layout and the page inside it share one round trip
 * per render pass.
 */
export const getSession = cache(async (): Promise<SessionState> => {
  const token = await getAccessToken();
  if (!token) return { status: "anonymous" };

  try {
    return { status: "member", user: await apiFetch<CurrentUser>("/api/me", { token }) };
  } catch (error) {
    if (error instanceof ApiError) {
      // Authenticated by Supabase, but with no row in `users` -- signup was
      // abandoned between creating the account and joining an organization.
      if (error.needsOrganization) return { status: "unprovisioned" };
      if (error.isUnauthenticated) return { status: "anonymous" };
    }
    // Anything else -- the backend being down, a malformed response -- is a
    // real fault. Let it reach the error boundary rather than masquerading as
    // a signed-out user and bouncing them to login.
    throw error;
  }
});

/** The signed-in user, or null. For pages that already know they are inside the shell. */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const session = await getSession();
  return session.status === "member" ? session.user : null;
}
