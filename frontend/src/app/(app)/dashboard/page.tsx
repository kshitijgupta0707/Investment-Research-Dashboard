import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Dashboard" };

/**
 * Placeholder for CR-20, which wires up recent queries, saved reports and the
 * watchlist widget. It exists now so the shell, the nav and the protected
 * layout have somewhere real to land.
 */
export default async function DashboardPage() {
  const user = await getCurrentUser();

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Recent research, saved reports and your watchlist."
      />

      <Card className="border-dashed bg-transparent">
        <CardContent className="py-10 text-center">
          <p className="text-sm text-muted-foreground">
            Signed in as <span className="text-foreground">{user?.email}</span>
          </p>
          <p className="mt-1.5 text-xs text-faint">
            This is a placeholder for the dashboard. It will be replaced with
            the actual dashboard once it is implemented.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
