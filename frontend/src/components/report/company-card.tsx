import type { CompanyCardContent } from "@/lib/api/types";

/**
 * One company's headline figures.
 *
 * Values arrive pre-formatted from the agent — "$2.1T", not 2100000000000 —
 * because unit conventions are a judgement about the reader, and the model has
 * the context to make it. Reformatting here would mean guessing twice.
 *
 * A metric with a null value is rendered as an em dash rather than dropped: the
 * absence of a P/E is itself informative for a loss-making company.
 */
export function CompanyCard({ content }: { content: CompanyCardContent }) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4">
      <header className="flex items-baseline gap-2.5">
        <span className="numeric text-[15px] font-semibold tracking-wider text-primary">
          {content.ticker}
        </span>
        {content.company_name ? (
          <span className="truncate text-xs text-muted-foreground">{content.company_name}</span>
        ) : null}
      </header>

      {content.metrics.length > 0 ? (
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
          {content.metrics.map((metric) => (
            <div key={metric.label}>
              <dt className="text-[10.5px] uppercase leading-tight tracking-wider text-faint">
                {metric.label}
              </dt>
              <dd className="numeric mt-1.5 text-[17px] font-medium tabular-nums">
                {metric.value ?? <span className="text-faint">—</span>}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-3 text-xs text-faint">No metrics were returned for this company.</p>
      )}
    </div>
  );
}
