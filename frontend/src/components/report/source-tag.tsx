import { ExternalLink, FileText, Link2, Newspaper } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Source, SourceType } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";

const ICONS: Record<SourceType, LucideIcon> = {
  api: Link2,
  article: Newspaper,
  filing: FileText,
};

/**
 * Where one section's figures came from.
 *
 * Every section carries its own sources -- attribution is per section, not per
 * report, because a report mixes a price feed, news and filings and the reader
 * needs to know which claim rests on which.
 *
 * `data_as_of` is shown whenever the provider gave one. Quotes on free tiers
 * are delayed, and PROJECT_PLAN §3.10 is explicit that nothing here may be
 * presented as live.
 */
export function SourceTag({ source }: { source: Source }) {
  const Icon = ICONS[source.type] ?? Link2;

  const label = (
    <>
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{source.label}</span>
      {source.data_as_of ? (
        <span className="numeric shrink-0 text-faint" title={absoluteTime(source.data_as_of)}>
          · as of {absoluteTime(source.data_as_of)}
        </span>
      ) : null}
    </>
  );

  const shared =
    "inline-flex max-w-full items-center gap-1.5 rounded-sm border border-border bg-surface px-2 py-1 text-[11px] text-muted-foreground";

  if (!source.url) {
    return <span className={shared}>{label}</span>;
  }

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`${shared} hover:border-primary-dim hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
    >
      {label}
      <ExternalLink className="h-2.5 w-2.5 shrink-0 text-faint" aria-hidden="true" />
    </a>
  );
}

/** A section's full attribution list. */
export function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;

  return (
    <div className="mt-4 flex flex-wrap gap-1.5 border-t border-hairline pt-3">
      {sources.map((source, index) => (
        <SourceTag key={`${source.label}-${index}`} source={source} />
      ))}
    </div>
  );
}
