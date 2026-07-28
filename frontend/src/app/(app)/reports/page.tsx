import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Saved reports" };

/** Placeholder. Replaced by CR-23. */
export default function ReportsPage() {
  return (
    <ComingSoon
      title="Saved reports"
      description="Every report saved in your workspace."
      cr="Coming in Next CR's"
      scope="Search and tag filtering, report detail with the full structured result, edit tags and delete — gated by the creator-or-admin rule."
    />
  );
}
