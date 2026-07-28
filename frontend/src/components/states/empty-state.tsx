import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  /** What is absent, stated plainly. */
  title: string;
  /** How to make it not absent. */
  hint: string;
  action?: { href: string; label: string };
  className?: string;
}

/**
 * The "nothing here yet" state.
 *
 * Always says what to do next, never just that a list is empty: a brand-new
 * org sees these on every panel of their first screen, and a wall of "No data"
 * teaches them nothing about the product.
 */
export function EmptyState({ icon: Icon, title, hint, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center px-4 py-8 text-center", className)}>
      <Icon className="h-5 w-5 text-faint" aria-hidden="true" />
      <p className="mt-3 text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 max-w-[38ch] text-xs leading-relaxed text-faint">{hint}</p>
      {action ? (
        <Link
          href={action.href}
          className="mt-4 rounded-sm text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}
