import {
  AlignLeft,
  Building2,
  LineChart,
  MessageSquareQuote,
  Sparkles,
  Table2,
  type LucideIcon,
} from "lucide-react";

import { PartialBanner } from "@/components/research/partial-banner";
import { Card, CardContent } from "@/components/ui/card";
import type { ResearchReport, Section, SectionType } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";

import { ConfidenceIndicator } from "./confidence-indicator";
import { DataFreshnessLabel } from "./data-freshness-label";
import { SectionContent } from "./section-content";
import { SourceList } from "./source-tag";

/** A mark per section type, so a long report is scannable. */
const SECTION_ICONS: Record<SectionType, LucideIcon> = {
  text: AlignLeft,
  table: Table2,
  chart: LineChart,
  company_card: Building2,
  sentiment: MessageSquareQuote,
};

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
    <article className="space-y-5">
      <PartialBanner failedTools={report.failed_tools} />

      <ReportSummary summary={report.summary} />

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

/** The answer, set apart from the evidence for it. */
function ReportSummary({ summary }: { summary: string }) {
  if (!summary.trim()) return null;

  return (
    <div className="relative overflow-hidden rounded-lg border border-primary/25 bg-primary/[0.055] p-5 pl-6">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-primary" />

      <p className="numeric mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-primary">
        <Sparkles className="h-3 w-3" aria-hidden="true" />
        Summary
      </p>

      <p className="text-[15px] leading-relaxed text-foreground">{summary}</p>
    </div>
  );
}

function ReportSection({ section, now }: { section: Section; now: number }) {
  const Icon = SECTION_ICONS[section.type] ?? AlignLeft;

  return (
    <Card className="bg-surface transition-shadow hover:shadow-card-hover">
      <CardContent className="pt-5">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-hairline pb-3">
          <div className="flex min-w-0 items-start gap-3">
            <span
              aria-hidden="true"
              className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border border-primary/25 bg-primary/[0.08] text-primary"
            >
              <Icon className="h-3.5 w-3.5" />
            </span>

            <div className="min-w-0">
              <h3 className="font-display text-[16px] font-semibold leading-tight tracking-[-0.015em]">
                {section.title}
              </h3>
              <DataFreshnessLabel sources={section.sources} now={now} className="mt-1 block" />
            </div>
          </div>

          <ConfidenceIndicator level={section.confidence} />
        </header>

        <SectionContent section={section} />
        <SourceList sources={section.sources} />
      </CardContent>
    </Card>
  );
}
