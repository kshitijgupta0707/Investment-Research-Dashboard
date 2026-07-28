import type { QueryStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STATUS: Record<QueryStatus, { color: string; label: string }> = {
  success: { color: "bg-up", label: "All sources answered" },
  partial: { color: "bg-primary", label: "Some sources failed — partial result" },
  failed: { color: "bg-down", label: "The query failed" },
};

/**
 * How a past query ended.
 *
 * A dot plus a `title`, not a coloured word: it sits in a dense list where a
 * third text column would crowd the query itself. The label carries the meaning
 * for screen readers, so colour is never the only signal.
 */
export function StatusDot({ status, className }: { status: QueryStatus; className?: string }) {
  const { color, label } = STATUS[status];

  return (
    <span className={cn("flex items-center", className)} title={label}>
      <span aria-hidden="true" className={cn("h-1.5 w-1.5 shrink-0 rounded-full", color)} />
      <span className="sr-only">{label}</span>
    </span>
  );
}
