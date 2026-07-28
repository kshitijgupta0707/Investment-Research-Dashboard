"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";
import type {
  ChartContent,
  CompanyCardContent,
  Section,
  SentimentContent,
  TableContent,
  TextContent,
} from "@/lib/api/types";

import { CompanyCard } from "./company-card";
import { Prose } from "./prose";
import { ComparisonTable } from "./comparison-table";
import { SentimentList } from "./sentiment-list";

/**
 * The charting library is ~100 kB and most reports have no chart section --
 * the agent is told to use one only when a price series was actually
 * retrieved. Loading it on demand keeps that cost off every other result.
 */
const PriceChart = dynamic(
  () => import("./price-chart").then((module) => module.PriceChart),
  { ssr: false, loading: () => <Skeleton className="h-[220px] w-full" /> },
);

/**
 * Renders one section's body, chosen by its declared `type`.
 *
 * This switch is the whole reason the Turn-2 schema is a fixed contract: the
 * frontend never inspects prose to work out what it is looking at. The
 * `assertNever` default makes adding a section type to the contract without
 * teaching this component about it a compile error rather than a blank space
 * in a report.
 *
 * The casts are safe because the backend validates `content` against the model
 * matching `type` before it is stored or returned -- a section is either fully
 * typed or rejected.
 */
export function SectionContent({ section }: { section: Section }) {
  switch (section.type) {
    case "text":
      return <Prose text={(section.content as TextContent).text} />;

    case "table":
      return <ComparisonTable content={section.content as TableContent} />;

    case "chart":
      return <PriceChart content={section.content as ChartContent} />;

    case "company_card":
      return <CompanyCard content={section.content as CompanyCardContent} />;

    case "sentiment":
      return <SentimentList content={section.content as SentimentContent} />;

    default:
      return assertNever(section.type);
  }
}

/**
 * Exhaustiveness check.
 *
 * Returns a readable fallback at runtime as well as failing at compile time: a
 * newer backend sending an unknown section type should degrade to a note, not
 * crash the page an analyst is reading.
 */
function assertNever(type: never) {
  return (
    <p className="text-xs text-faint">
      This section type ({String(type)}) is not supported by this version of the app.
    </p>
  );
}

