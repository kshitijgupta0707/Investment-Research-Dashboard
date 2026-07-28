import Link from "next/link";

import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

interface TagListProps {
  tags: string[];
  /** Show at most this many, then a "+n" for the rest. */
  max?: number;
  /** Link each tag to a filtered report list. */
  linked?: boolean;
  className?: string;
}

/**
 * A report's tags.
 *
 * Tags are normalised to lower case by the backend, so they are rendered as
 * stored -- title-casing them here would misrepresent what a tag filter
 * actually matches.
 */
export function TagList({ tags, max, linked = false, className }: TagListProps) {
  if (tags.length === 0) return null;

  const shown = max ? tags.slice(0, max) : tags;
  const hidden = tags.length - shown.length;

  return (
    <span className={cn("flex flex-wrap items-center gap-1", className)}>
      {shown.map((tag) =>
        linked ? (
          <Link
            key={tag}
            href={`${routes.reports}?tag=${encodeURIComponent(tag)}`}
            className="numeric rounded-sm border border-border bg-surface px-1.5 py-0.5 text-[10px] text-muted-foreground hover:border-primary-dim hover:text-foreground"
          >
            {tag}
          </Link>
        ) : (
          <span
            key={tag}
            className="numeric rounded-sm border border-border bg-surface px-1.5 py-0.5 text-[10px] text-muted-foreground"
          >
            {tag}
          </span>
        ),
      )}
      {hidden > 0 ? (
        <span className="numeric text-[10px] text-faint" title={tags.join(", ")}>
          +{hidden}
        </span>
      ) : null}
    </span>
  );
}
