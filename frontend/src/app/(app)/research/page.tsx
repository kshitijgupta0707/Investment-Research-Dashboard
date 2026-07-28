import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { ResearchWorkspace } from "@/components/research/research-workspace";
import { MAX_QUERY_CHARS } from "@/lib/research/schema";

export const metadata: Metadata = { title: "New research" };

/**
 * The core flow.
 *
 * `?q=` pre-fills the box, which is how the dashboard's "Analyse" links and the
 * compare-companies action hand a question over. It is read on the server so
 * the first paint already carries the text.
 */
export default function ResearchPage({ searchParams }: { searchParams: { q?: string } }) {
  const initialQuery = (searchParams.q ?? "").slice(0, MAX_QUERY_CHARS);

  return (
    <>
      <PageHeader
        title="New research"
        description="Ask in plain language. The agent decides which sources the question needs, queries them in parallel, and attributes every figure it reports."
      />

      <ResearchWorkspace initialQuery={initialQuery} />
    </>
  );
}
