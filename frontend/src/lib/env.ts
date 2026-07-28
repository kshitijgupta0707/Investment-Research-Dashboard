/**
 * Environment access, resolved in one place.
 *
 * `NEXT_PUBLIC_*` values are inlined into the browser bundle at build time, so
 * they must be referenced as complete literals -- `process.env[key]` with a
 * computed key silently yields undefined. Hence the explicit map below rather
 * than a loop.
 *
 * Reading a missing value throws here, at first use, instead of surfacing later
 * as an opaque "fetch failed" against `undefined/api/...`.
 */

const values = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
  supabaseKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
} as const;

const variableNames: Record<keyof typeof values, string> = {
  apiBaseUrl: "NEXT_PUBLIC_API_BASE_URL",
  supabaseUrl: "NEXT_PUBLIC_SUPABASE_URL",
  supabaseKey: "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
};

function required(name: keyof typeof values): string {
  const value = values[name];
  if (!value) {
    throw new Error(
      `${variableNames[name]} is not set. Copy frontend/.env.local.example to ` +
        `frontend/.env.local and fill it in.`,
    );
  }
  return value;
}

export const env = {
  get apiBaseUrl() {
    return required("apiBaseUrl");
  },
  get supabaseUrl() {
    return required("supabaseUrl");
  },
  get supabaseKey() {
    return required("supabaseKey");
  },
};
