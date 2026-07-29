import type { Metadata } from "next";
import { Suspense } from "react";

import { QuickActions } from "@/components/dashboard/quick-actions";
import { RecentQueries } from "@/components/dashboard/recent-queries";
import { RecentReports } from "@/components/dashboard/recent-reports";
import { WatchlistWidget } from "@/components/dashboard/watchlist-widget";
import { Widget, WidgetSkeleton } from "@/components/dashboard";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const user = await getCurrentUser();

  // Captured once and passed down, so every relative timestamp on the page is
  // measured from the same instant -- and so a server render and its hydration
  // cannot disagree about what "3 hours ago" means.
  const now = Date.now();

  return (
    <>
      <PageHeader
        title={greeting(user?.name, user?.email)}
        description="Recent research, saved reports and the companies you follow."
      />

      <div className="space-y-6">
        <QuickActions />

        {/*
         * Each widget fetches its own endpoint and streams in when ready, so
         * the page paints as soon as the shell is known rather than waiting on
         * the slowest of three calls. They also fail independently.
         */}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Suspense fallback={<Widget title="Recent queries"><WidgetSkeleton /></Widget>}>
              <RecentQueries now={now} />
            </Suspense>
          </div>

          <Suspense fallback={<Widget title="Watchlist"><WidgetSkeleton rows={4} /></Widget>}>
            <WatchlistWidget />
          </Suspense>

          <div className="lg:col-span-3">
            <Suspense fallback={<Widget title="Saved reports"><WidgetSkeleton /></Widget>}>
              <RecentReports now={now} />
            </Suspense>
          </div>
        </div>
      </div>
    </>
  );
}

/**
 * Greet by first name, falling back to the address.
 *
 * The stored name wins when there is one: deriving "Analyst" from
 * `analyst@northwind.test` is technically a name and obviously not the
 * person's. The address is only used when the account has no name at all,
 * which happens when someone signs up without filling the optional field.
 */
function greeting(name: string | null | undefined, email: string | undefined): string {
  const firstName = name?.trim().split(/\s+/)[0];
  if (firstName) return `Welcome back, ${firstName}`;

  const handle = email?.split("@")[0]?.split(/[._-]/)[0];
  if (!handle) return "Dashboard";
  return `Welcome back, ${handle.charAt(0).toUpperCase()}${handle.slice(1)}`;
}
