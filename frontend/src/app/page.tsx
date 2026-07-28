import { redirect } from "next/navigation";

import { routes } from "@/lib/routes";

/**
 * The root has no content of its own.
 *
 * Middleware has already decided whether this request has a session, so it will
 * have been rewritten to login before reaching here if not.
 */
export default function RootPage() {
  redirect(routes.dashboard);
}
