"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api/client";
import { messageFor } from "@/lib/api/errors";
import type { Membership } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { createClient } from "@/lib/supabase/server";

import { parseLogin, parseSignup, type FormState } from "./schema";

/**
 * Sign in with email and password.
 *
 * Membership is deliberately not checked here. A user who authenticated but was
 * never provisioned into an organization is a real state -- they abandoned
 * signup partway -- and the app layout handles it by sending them back to
 * finish, rather than this action inventing a second failure mode.
 */
export async function login(_previous: FormState, formData: FormData): Promise<FormState> {
  const parsed = parseLogin(formData);
  if (!parsed.ok) return { error: parsed.error };

  const supabase = createClient();
  const { error } = await supabase.auth.signInWithPassword({
    email: parsed.value.email,
    password: parsed.value.password,
  });

  if (error) {
    // Supabase says "Invalid login credentials" for both a wrong password and
    // an unknown address, which is the right amount to disclose. Passed through.
    return { error: error.message };
  }

  revalidatePath("/", "layout");
  redirect(nextDestination(formData));
}

/**
 * Create the auth user, then provision them into an organization.
 *
 * Two systems, in order: Supabase owns the credentials, the backend owns
 * membership and roles. The second step needs the token from the first, so this
 * cannot be split across two round trips from the client without leaving an
 * orphaned auth user behind on a refresh.
 */
export async function signup(_previous: FormState, formData: FormData): Promise<FormState> {
  const parsed = parseSignup(formData);
  if (!parsed.ok) return { error: parsed.error };

  const { email, password, name, intent, orgName, inviteCode } = parsed.value;
  const supabase = createClient();

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { name } },
  });

  if (error) return { error: error.message };

  // With email confirmation switched on, Supabase returns no session. There is
  // no token to provision with, so stop here and say so plainly.
  const token = data.session?.access_token;
  if (!token) {
    return {
      error:
        "Check your email to confirm your address, then sign in to finish setting up " +
        "your workspace.",
    };
  }

  try {
    if (intent === "create") {
      await apiFetch<Membership>("/api/org", {
        token,
        method: "POST",
        body: { name: orgName, user_name: name || null },
      });
    } else {
      await apiFetch<Membership>("/api/org/join", {
        token,
        method: "POST",
        body: { code: inviteCode, user_name: name || null },
      });
    }
  } catch (cause) {
    // The auth user now exists without a membership. Signing them back out
    // keeps the app from rendering a half-provisioned session; the address is
    // still taken, so the message has to say what to do next.
    await supabase.auth.signOut();
    return { error: messageFor(cause) };
  }

  revalidatePath("/", "layout");
  redirect(routes.dashboard);
}

export async function logout(): Promise<void> {
  const supabase = createClient();
  await supabase.auth.signOut();
  revalidatePath("/", "layout");
  redirect(routes.login);
}

/** Where login should land, honouring the `next` param the middleware set. */
function nextDestination(formData: FormData): string {
  const next = formData.get("next");
  return typeof next === "string" && next.startsWith("/") ? next : routes.dashboard;
}
