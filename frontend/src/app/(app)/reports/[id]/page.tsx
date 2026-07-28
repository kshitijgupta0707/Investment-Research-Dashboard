import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ReportView } from "@/components/report/report-view";
import { DeleteReport } from "@/components/reports/delete-report";
import { EditTags } from "@/components/reports/edit-tags";
import { ReportMeta } from "@/components/reports/report-meta";
import { ApiError } from "@/lib/api/errors";
import { getReport } from "@/lib/api/resources";
import { getCurrentUser } from "@/lib/auth/session";
import { canModify, modifyDeniedReason } from "@/lib/reports/permissions";
import { routes } from "@/lib/routes";
import { truncate } from "@/lib/format";

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  try {
    const report = await getReport(params.id);
    return { title: truncate(report.query_text, 60) };
  } catch {
    return { title: "Report" };
  }
}

/**
 * One saved report, re-rendered from its stored JSON.
 *
 * The same `ReportView` the research page uses, so a saved report and a fresh
 * one are identical by construction -- that is the point of storing the
 * structured result rather than prose.
 *
 * A report belonging to another organization comes back as 404 from the API,
 * not 403, so an id from a different tenant is indistinguishable from one that
 * never existed. That is deliberate on the backend and passed straight through
 * here.
 */
export default async function ReportDetailPage({ params }: { params: { id: string } }) {
  const user = await getCurrentUser();

  let report;
  try {
    report = await getReport(params.id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const editable = user ? canModify(report, user) : false;
  const deniedReason = user ? modifyDeniedReason(report, user) : null;
  const now = Date.now();

  return (
    <>
      <Link
        href={routes.reports}
        className="mb-6 inline-flex items-center gap-1.5 rounded-sm text-[12px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
        All reports
      </Link>

      <h1 className="mb-4 font-display text-xl font-medium leading-snug tracking-[-0.02em]">
        {report.query_text}
      </h1>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <EditTags
          reportId={report.id}
          tags={report.tags}
          canEdit={editable}
          deniedReason={deniedReason}
        />
        {editable ? (
          <DeleteReport reportId={report.id} queryText={truncate(report.query_text, 70)} />
        ) : null}
      </div>

      <div className="space-y-6">
        <ReportMeta report={report} now={now} />
        <ReportView report={report.structured_result} />
      </div>
    </>
  );
}
