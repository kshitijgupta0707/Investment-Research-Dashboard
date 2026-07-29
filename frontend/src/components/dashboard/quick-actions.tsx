import Link from "next/link";
import { GitCompareArrows, Search } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { routes } from "@/lib/routes";

interface Action {
  href: string;
  icon: LucideIcon;
  title: string;
  detail: string;
}

const COMPARE_QUERY =
  "Compare revenue growth, margins and valuation across NVIDIA, AMD and Intel, and flag the key risks for each.";

const ACTIONS: readonly Action[] = [
  {
    href: routes.research,
    icon: Search,
    title: "New research",
    detail: "Ask anything in plain language",
  },
  {
    href: `${routes.research}?q=${encodeURIComponent(COMPARE_QUERY)}`,
    icon: GitCompareArrows,
    title: "Compare companies",
    detail: "Start from a multi-company template",
  },
];

/**
 * The two ways in.
 *
 * "Compare companies" is the same page with the box pre-filled rather than a
 * separate flow -- there is one query endpoint, and a second UI implying
 * otherwise would be a lie about the architecture.
 */
export function QuickActions() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {ACTIONS.map(({ href, icon: Icon, title, detail }) => (
        <Link
          key={title}
          href={href}
          className="group flex items-start gap-3 rounded-lg border border-border bg-surface p-4 shadow-card transition-all hover:-translate-y-px hover:border-primary/45 hover:shadow-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span
            aria-hidden="true"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-primary/25 bg-primary/[0.08] text-primary transition-colors group-hover:bg-primary/[0.14]"
          >
            <Icon className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-sm font-medium group-hover:text-primary">{title}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">{detail}</span>
          </span>
        </Link>
      ))}
    </div>
  );
}
