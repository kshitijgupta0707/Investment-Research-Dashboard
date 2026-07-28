import type { Metadata } from "next";
import { FileText, SearchX } from "lucide-react";

import { WidgetError } from "@/components/dashboard";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/reports/pagination";
import { ReportCard } from "@/components/reports/report-card";
import { ReportFilters } from "@/components/reports/report-filters";
import { messageFor } from "@/lib/api/errors";
import { listReports, REPORTS_PER_PAGE } from "@/lib/api/resources";
import { routes } from "@/lib/routes";

export const metadata: Metadata = { title: "Saved reports" };

interface SearchParams {
  q?: string;
  tag?: string;
  offset?: string;
}

/**
 * Every report saved in the organization.
 *
 * Org-scoped rather than per-user: a workspace is shared, so a colleague's
 * saved work belongs here. Search and tag filters come from the URL and are
 * applied by the API, so the list is filtered at the database rather than
 * fetched whole and hidden in the browser.
 */
export default async function ReportsPage({ searchParams }: { searchParams: SearchParams }) {
  const q = searchParams.q?.trim() || undefined;
  const tag = searchParams.tag?.trim() || undefined;
  const offset = Math.max(0, Number.parseInt(searchParams.offset ?? "0", 10) || 0);
  const now = Date.now();

  let page;
  try {
    page = await listReports({ q, tag, offset, limit: REPORTS_PER_PAGE });
  } catch (error) {
    return (
      <>
        <PageHeader title="Saved reports" description="Every report saved in your workspace." />
        <WidgetError detail={messageFor(error)} />
      </>
    );
  }

  const filtered = Boolean(q || tag);

  return (
    <>
      <PageHeader
        title="Saved reports"
        description="Shared with everyone in your workspace. Anyone can read them; only the author or an admin can change one."
      />

      <div className="space-y-5">
        <ReportFilters activeTag={tag} />

        {page.items.length === 0 ? (
          <NoResults filtered={filtered} q={q} tag={tag} />
        ) : (
          <>
            <ul className="space-y-3">
              {page.items.map((report) => (
                <li key={report.id}>
                  <ReportCard report={report} now={now} />
                </li>
              ))}
            </ul>

            <Pagination
              total={page.total}
              limit={page.limit}
              offset={page.offset}
              hrefFor={(next) => buildHref({ q, tag, offset: next })}
            />
          </>
        )}
      </div>
    </>
  );
}

/**
 * Empty because nothing matched, or empty because nothing exists.
 *
 * They call for different next steps -- clearing a filter versus running a
 * first query -- so they are different states rather than one "no data" line.
 */
function NoResults({ filtered, q, tag }: { filtered: boolean; q?: string; tag?: string }) {
  if (!filtered) {
    return (
      <EmptyState
        icon={FileText}
        title="No reports saved yet"
        hint="Run a query and save the result — it keeps the figures exactly as they were when you asked."
        action={{ href: routes.research, label: "Start researching" }}
      />
    );
  }

  return (
    <EmptyState
      icon={SearchX}
      title="Nothing matched"
      hint={
        tag && q
          ? `No report tagged "${tag}" mentions "${q}".`
          : tag
            ? `No report is tagged "${tag}".`
            : `No saved report mentions "${q}". Search matches the question that was asked, not the report body.`
      }
      action={{ href: routes.reports, label: "Clear filters" }}
    />
  );
}

/** Keep the active filters when paging. */
function buildHref({ q, tag, offset }: { q?: string; tag?: string; offset: number }): string {
  const search = new URLSearchParams();
  if (q) search.set("q", q);
  if (tag) search.set("tag", tag);
  if (offset > 0) search.set("offset", String(offset));
  const query = search.toString();
  return query ? `${routes.reports}?${query}` : routes.reports;
}
