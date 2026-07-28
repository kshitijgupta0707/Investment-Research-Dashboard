import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "New research" };

/** Placeholder. Replaced by CR-21. */
export default function ResearchPage() {
  return (
    <ComingSoon
      title="New research"
      description="Ask a question in plain language."
      cr="Coming in Next CR's"
      scope="The query box, a loading state while the agent plans and runs its tools, and the structured result rendered inline."
    />
  );
}
