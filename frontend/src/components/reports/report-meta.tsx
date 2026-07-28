import Link from "next/link";
import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ReportDetail } from "@/lib/api/types";
import { absoluteTime, isStale } from "@/lib/format";
import { routes } from "@/lib/routes";

/**
 * The provenance header above a saved report.
 *
 * PROJECT_PLAN §3.10 asks for this explicitly: a saved report is a frozen
 * snapshot, correct for equity research but easy to misread as current. So the
 * date it speaks for is stated prominently, a staleness note appears past a
 * day, and re-running is offered right beside it -- which produces a *new*
 * report and leaves this one intact.
 */
export function ReportMeta({ report, now }: { report: ReportDetail; now: number }) {
  const generated = report.structured_result.generated_at;
  const stale = isStale(generated, now);

  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-hairline pb-4">
      <div className="min-w-0">
        <p className="numeric text-[11px] text-muted-foreground">
          Generated {absoluteTime(generated)} — figures are as of that time
        </p>
        <p className="numeric mt-1 text-[10.5px] text-faint">Saved by {report.created_by_email}</p>

        {stale ? (
          <p className="mt-2 border-l-2 border-primary bg-primary/[0.06] px-3 py-2 text-[12px] leading-relaxed text-muted-foreground">
            This report is more than a day old. Prices and coverage will have moved since —
            re-run it for current figures.
          </p>
        ) : null}
      </div>

      <Button asChild variant="secondary" size="sm" className="shrink-0 gap-2">
        <Link href={`${routes.research}?q=${encodeURIComponent(report.query_text)}`}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Re-run this query
        </Link>
      </Button>
    </div>
  );
}
