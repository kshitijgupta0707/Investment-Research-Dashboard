import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { env } from "@/lib/env";

/**
 * Supabase client for server components, route handlers and server actions.
 *
 * The session lives in cookies so it is readable on the server; this reads and
 * writes them through Next's cookie store.
 */
export function createClient() {
  const cookieStore = cookies();

  return createServerClient(env.supabaseUrl, env.supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // Server components cannot set cookies. The middleware refreshes the
          // session on every request, so it is safe to ignore here.
        }
      },
    },
  });
}

/**
 * The current access token, or null when signed out.
 *
 * Every authenticated backend call goes through this, so no component reaches
 * into the session object itself.
 */
export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
