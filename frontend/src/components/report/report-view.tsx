import { PartialBanner } from "@/components/research/partial-banner";
import { Card, CardContent } from "@/components/ui/card";
import type { ResearchReport, Section } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";

import { ConfidenceIndicator } from "./confidence-indicator";
import { DataFreshnessLabel } from "./data-freshness-label";
import { SectionContent } from "./section-content";
import { SourceList } from "./source-tag";

/**
 * A whole report, rendered from the fixed Turn-2 schema.
 *
 * Shared by the research page and — from CR-23 — report detail, so a saved
 * report and a fresh one are guaranteed to look identical. That is the point of
 * storing the structured result rather than prose.
 */
export function ReportView({ report }: { report: ResearchReport }) {
  // Captured once so every freshness label on the page measures from the same
  // instant, and so a server render and its hydration agree.
  const now = Date.now();

  return (
    <article className="space-y-6">
      <PartialBanner failedTools={report.failed_tools} />

      <p className="text-[15px] leading-relaxed">{report.summary}</p>

      {report.sections.map((section, index) => (
        <ReportSection key={`${section.title}-${index}`} section={section} now={now} />
      ))}

      {/* A report is a snapshot. §3.10 asks for the date it speaks for to be
          stated, not inferred from when the page was opened. */}
      <footer className="numeric border-t border-hairline pt-3 text-[10.5px] text-faint">
        Generated {absoluteTime(report.generated_at)} — figures are as of that time.
      </footer>
    </article>
  );
}

function ReportSection({ section, now }: { section: Section; now: number }) {
  return (
    <Card className="bg-surface/40">
      <CardContent className="pt-5">
        <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-[15px] font-medium tracking-tight">
              {section.title}
            </h3>
            <DataFreshnessLabel sources={section.sources} now={now} className="mt-0.5 block" />
          </div>
          <ConfidenceIndicator level={section.confidence} />
        </header>

        <SectionContent section={section} />
        <SourceList sources={section.sources} />
      </CardContent>
    </Card>
  );
}
