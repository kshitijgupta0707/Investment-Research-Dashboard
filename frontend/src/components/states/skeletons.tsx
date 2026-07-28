import { Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Loading placeholders shaped like the content they stand in for.
 *
 * Matching the real layout is the point: a skeleton that is the wrong shape
 * causes the page to jump when data arrives, which is worse than a spinner.
 * All of these are `aria-hidden` and paired with a live region on the route's
 * `loading.tsx`, so a screen reader hears "loading" once rather than reading
 * out a wall of empty boxes.
 */

export function PageHeaderSkeleton() {
  return (
    <div className="mb-8" aria-hidden="true">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="mt-2.5 h-4 w-96 max-w-full" />
    </div>
  );
}

/** Rows inside a bordered list, as used by reports, watchlist and members. */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <Card key={index} className="bg-surface/40">
          <CardContent className="py-4">
            <Skeleton className="h-4 w-3/4" />
            <div className="mt-3 flex gap-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/** A dense table-like list: watchlist rows, member rows. */
export function RowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-hairline rounded-lg border border-border" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-4 px-4 py-3">
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

/** A full report: summary paragraph then a few section cards. */
export function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>

      {Array.from({ length: 3 }, (_, index) => (
        <Card key={index} className="bg-surface/40">
          <CardContent className="space-y-3 pt-5">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-16" />
            </div>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-6 w-48" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/**
 * States the wait, on screen and to assistive technology.
 *
 * Visible rather than `sr-only`: skeleton boxes alone are ambiguous -- they
 * read as much like a broken layout as a pending one -- and on a fast local
 * backend they can flash by with nothing to explain what happened. The live
 * region does double duty for screen readers, which is why the skeletons
 * themselves stay hidden from the accessibility tree.
 */
export function LoadingAnnouncement({ label }: { label: string }) {
  return (
    <p
      role="status"
      aria-live="polite"
      className="mb-4 flex items-center gap-2 text-[12px] text-muted-foreground"
    >
      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" aria-hidden="true" />
      {label}…
    </p>
  );
}
