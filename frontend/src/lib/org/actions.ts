"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api/client";
import { messageFor } from "@/lib/api/errors";
import type { Invite } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { getAccessToken } from "@/lib/supabase/server";

import type { InviteState } from "./schema";

/**
 * Mint an invite code.
 *
 * Takes no input: the code, its organization and its lifetime are all decided
 * server-side. Letting a client propose a code would let it pick a guessable
 * one.
 *
 * Admin-only, enforced by the API. A non-admin reaching this gets a 403 back
 * as an error message rather than a silent no-op.
 */
export async function createInvite(
  _previous: InviteState,
  _formData: FormData,
): Promise<InviteState> {
  try {
    const invite = await apiFetch<Invite>("/api/org/invites", {
      token: await getAccessToken(),
      method: "POST",
    });

    revalidatePath(routes.organization);
    return { status: "created", code: invite.code };
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }
}

/** Withdraw a live invite. Revoking twice is a 404 -- it is already inactive. */
export async function revokeInvite(
  _previous: InviteState,
  formData: FormData,
): Promise<InviteState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { status: "error", message: "Missing invite id." };

  try {
    await apiFetch<Invite>(`/api/org/invites/${id}`, {
      token: await getAccessToken(),
      method: "DELETE",
    });

    revalidatePath(routes.organization);
    return { status: "revoked" };
  } catch (error) {
    return { status: "error", message: messageFor(error) };
  }
}
