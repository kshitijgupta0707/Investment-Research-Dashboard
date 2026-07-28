import { redirect } from "next/navigation";

import { FinishSetup } from "@/components/shell/finish-setup";
import { AppShell } from "@/components/shell/app-shell";
import { getSession } from "@/lib/auth/session";
import { routes } from "@/lib/routes";

/**
 * The protected half of the app.
 *
 * Middleware already turned away requests with no session; this resolves the
 * membership only the backend knows about. The unprovisioned case *renders*
 * rather than redirecting -- middleware would bounce a valid session straight
 * back here, and the two would trade redirects until the browser gave up.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  if (session.status === "anonymous") redirect(routes.login);
  if (session.status === "unprovisioned") return <FinishSetup />;

  return <AppShell user={session.user}>{children}</AppShell>;
}
