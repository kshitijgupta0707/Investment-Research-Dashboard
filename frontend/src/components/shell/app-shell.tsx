import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";
import type { CurrentUser } from "@/lib/api/types";
import { routes } from "@/lib/routes";

import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";

/**
 * The signed-in frame: a fixed rail on the left, page content on the right.
 *
 * The rail becomes a top bar below `lg`, where a 240px column would leave too
 * little room for a comparison table.
 */
export function AppShell({ user, children }: { user: CurrentUser; children: React.ReactNode }) {
  return (
    <div className="lg:grid lg:min-h-screen lg:grid-cols-[240px_1fr]">
      <div className="flex flex-col gap-6 border-b border-border bg-surface/40 p-4 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:p-5">
        <Link
          href={routes.dashboard}
          className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <BrandMark />
        </Link>

        <div className="flex-1">
          <SidebarNav role={user.role} />
        </div>

        <UserMenu user={user} />
      </div>

      <main className="min-w-0 p-6 lg:p-10">{children}</main>
    </div>
  );
}
