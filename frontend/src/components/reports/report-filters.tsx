"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { Loader2, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { routes } from "@/lib/routes";

/**
 * Keyword search and tag filter.
 *
 * State lives in the URL rather than in the component: a filtered list is then
 * shareable, survives a refresh, and is rendered on the server with the filter
 * already applied -- rather than fetching everything and hiding rows.
 */
export function ReportFilters({ activeTag }: { activeTag?: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [query, setQuery] = useState(params.get("q") ?? "");

  function apply(next: { q?: string; tag?: string }) {
    const search = new URLSearchParams();
    const q = next.q ?? query;
    const tag = "tag" in next ? next.tag : (activeTag ?? undefined);

    if (q.trim()) search.set("q", q.trim());
    if (tag) search.set("tag", tag);
    // Any change to the filters invalidates the current page number.

    startTransition(() => {
      router.push(search.toString() ? `${routes.reports}?${search}` : routes.reports);
    });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          apply({});
        }}
        className="flex flex-1 items-center gap-2"
      >
        <div className="relative min-w-[200px] flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search saved reports…"
            aria-label="Search saved reports"
            className="h-9 border-border bg-surface pl-9 text-[13px]"
          />
        </div>

        <Button type="submit" size="sm" className="h-9 px-4" disabled={pending}>
          {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : "Search"}
        </Button>
      </form>

      {activeTag ? (
        <button
          type="button"
          onClick={() => apply({ tag: undefined })}
          className="numeric inline-flex items-center gap-1.5 rounded-sm border border-primary bg-primary/10 px-2 py-1 text-[11px] text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          tag: {activeTag}
          <X className="h-3 w-3" aria-hidden="true" />
          <span className="sr-only">Clear tag filter</span>
        </button>
      ) : null}
    </div>
  );
}
