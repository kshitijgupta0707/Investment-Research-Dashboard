import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  /** Builds the href for a given offset, preserving the current filters. */
  hrefFor: (offset: number) => string;
}

/**
 * Previous / next over an offset-paginated list.
 *
 * Links rather than buttons, so a page is bookmarkable and the browser's own
 * back button does the obvious thing. `total` is the pre-pagination count the
 * API returns, which is what makes "showing 1–20 of 47" possible at all.
 */
export function Pagination({ total, limit, offset, hrefFor }: PaginationProps) {
  if (total <= limit) return null;

  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  const hasPrevious = offset > 0;
  const hasNext = last < total;

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between border-t border-hairline pt-4"
    >
      <p className="numeric text-[11px] text-faint">
        Showing {first}–{last} of {total}
      </p>

      <div className="flex items-center gap-2">
        <PageLink
          href={hrefFor(Math.max(0, offset - limit))}
          disabled={!hasPrevious}
          label="Previous page"
        >
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Previous
        </PageLink>

        <PageLink href={hrefFor(offset + limit)} disabled={!hasNext} label="Next page">
          Next
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        </PageLink>
      </div>
    </nav>
  );
}

function PageLink({
  href,
  disabled,
  label,
  children,
}: {
  href: string;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  const classes = cn(
    "inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-[12px]",
    disabled
      ? "cursor-not-allowed text-faint opacity-50"
      : "text-muted-foreground hover:border-primary-dim hover:text-foreground",
  );

  if (disabled) {
    return (
      <span className={classes} aria-disabled="true">
        {children}
      </span>
    );
  }

  return (
    <Link href={href} aria-label={label} className={classes}>
      {children}
    </Link>
  );
}
