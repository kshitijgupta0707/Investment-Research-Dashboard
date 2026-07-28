import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Report" };

/**
 * Placeholder. Replaced by CR-23.
 *
 * The dashboard already links every saved report here, so the route has to
 * exist even before the page does -- otherwise the most obvious thing to click
 * on the landing screen is a 404.
 */
export default function ReportDetailPage() {
  return (
    <ComingSoon
      title="Report"
      description="The saved result, re-rendered from its stored JSON."
      cr="Coming in Next CRs"
      scope="The full structured report — cards, tables, charts, sentiment and per-section sources — plus a 'generated on' header, a re-run action, and edit-tags and delete gated by the creator-or-admin rule."
    />
  );
}
