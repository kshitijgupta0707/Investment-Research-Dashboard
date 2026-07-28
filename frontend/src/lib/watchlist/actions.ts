"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";
import { messageFor } from "@/lib/api/errors";
import type { WatchlistEntry } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { getAccessToken } from "@/lib/supabase/server";

import { MAX_TICKER_CHARS, TICKER_PATTERN, type WatchlistState } from "./schema";

/**
 * Pin a company.
 *
 * Re-adding something already pinned is not an error -- the API returns 200
 * with the existing entry rather than a 409, because the user pressed a button
 * and got the state they wanted. So there is nothing to report here either.
 */
export async function addTicker(
  _previous: WatchlistState,
  formData: FormData,
): Promise<WatchlistState> {
  const ticker = String(formData.get("ticker") ?? "").trim().toUpperCase();
  const companyName = String(formData.get("company_name") ?? "").trim();

  if (!ticker) return { status: "error", message: "Enter a ticker symbol." };
  if (ticker.length > MAX_TICKER_CHARS) {
    return { status: "error", message: `Tickers are ${MAX_TICKER_CHARS} characters or fewer.` };
  }
  if (!TICKER_PATTERN.test(ticker)) {
    return {
      status: "error",
      message: "A ticker may contain only letters, digits, dots and hyphens.",
    };
  }

  try {
    await apiFetch<WatchlistEntry>("/api/watchlist", {
      token: await getAccessToken(),
      method: "POST",
      body: { ticker, company_name: companyName || null },
    });
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }

  revalidatePath(routes.watchlist);
  revalidatePath(routes.dashboard);

  return { status: "added", ticker };
}

/** Unpin a company. Another user's entry is a 404 -- watchlists are personal. */
export async function removeTicker(
  _previous: WatchlistState,
  formData: FormData,
): Promise<WatchlistState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { status: "error", message: "Missing entry id." };

  try {
    await apiFetch<{ id: string }>(`/api/watchlist/${id}`, {
      token: await getAccessToken(),
      method: "DELETE",
    });
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }

  revalidatePath(routes.watchlist);
  revalidatePath(routes.dashboard);

  return { status: "removed" };
}
