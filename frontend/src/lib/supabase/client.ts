import { createBrowserClient } from "@supabase/ssr";

import { env } from "@/lib/env";

/**
 * Supabase client for client components.
 *
 * `createBrowserClient` memoises internally, so calling this per render is
 * cheap and avoids passing a client down through props.
 */
export function createClient() {
  return createBrowserClient(env.supabaseUrl, env.supabaseKey);
}
