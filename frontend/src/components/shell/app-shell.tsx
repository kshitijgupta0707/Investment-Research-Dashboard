import Link from "next/link";

import { BrandMark, PRODUCT_NAME } from "@/components/brand/brand-mark";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import type { CurrentUser } from "@/lib/api/types";
import { routes } from "@/lib/routes";

import { CompactNav } from "./compact-nav";
import { PageTransition } from "./page-transition";
import { SidebarNav } from "./sidebar-nav";
import { UserMenu } from "./user-menu";

interface AppShellProps {
  user: CurrentUser;
  /** The organization this session belongs to, named in the rail. */
  orgName?: string | null;
  children: React.ReactNode;
}

/** The signed-in frame. The rail becomes a top bar below `md`. */
export function AppShell({ user, orgName, children }: AppShellProps) {
  return (
    <div className="md:grid md:min-h-screen md:grid-cols-[212px_1fr] lg:grid-cols-[248px_1fr]">
      {/* Tighter spacing and padding under `md`: the rail becomes a bar there,
          and desktop breathing room turns into a screenful of chrome above the
          content on a phone. */}
      <div className="flex min-w-0 flex-col gap-3 border-b border-border bg-surface/50 p-3 backdrop-blur-sm md:sticky md:top-0 md:h-screen md:gap-5 md:border-b-0 md:border-r md:p-4 lg:gap-6 lg:p-5">
        <div className="flex items-center justify-between gap-2">
          <Link
            href={routes.dashboard}
            aria-label={`${PRODUCT_NAME} home`}
            className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <BrandMark />
          </Link>
          {/* Below `xs` these two carry the destinations that no longer fit in
              the bar. Hidden from `xs` up, where the bar shows them itself. */}
          <div className="flex items-center gap-0.5">
            <CompactNav role={user.role} />
            <ThemeToggle />
          </div>
        </div>

        <div className="md:flex-1">
          <SidebarNav role={user.role} />
        </div>

        <UserMenu user={user} orgName={orgName} />
      </div>

      {/* The aurora wash stops a full-height content column reading as a flat
          fill. It sits behind everything and is barely perceptible. */}
      <main className="bg-aurora min-w-0 p-5 md:p-7 lg:p-10">
        <PageTransition>{children}</PageTransition>
      </main>
    </div>
  );
}
