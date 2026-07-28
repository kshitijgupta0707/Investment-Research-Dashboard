"use client";

import { useState } from "react";
import { useFormStatus } from "react-dom";
import { CornerDownLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  EXAMPLE_QUERIES,
  MAX_QUERY_CHARS,
  MIN_QUERY_CHARS,
  QUERY_WARN_AT,
} from "@/lib/research/schema";
import { cn } from "@/lib/utils";

interface QueryFormProps {
  /** Pre-filled from `?q=`, or carried back after a failed run. */
  initialQuery?: string;
  /** Offer the examples only when there is nothing else on screen. */
  showExamples?: boolean;
}

export function QueryForm({ initialQuery = "", showExamples = false }: QueryFormProps) {
  const [query, setQuery] = useState(initialQuery);
  const { pending } = useFormStatus();

  const length = query.trim().length;
  const tooLong = length > MAX_QUERY_CHARS;
  const submittable = length >= MIN_QUERY_CHARS && !tooLong;

  return (
    <div>
      <label htmlFor="query_text" className="sr-only">
        Your research question
      </label>

      <Textarea
        id="query_text"
        name="query_text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        disabled={pending}
        rows={3}
        placeholder="Compare NVIDIA, AMD and Intel on revenue growth, and flag the key risks…"
        aria-describedby="query-counter"
        className={cn(
          "resize-y border-border bg-surface text-sm leading-relaxed focus-visible:bg-surface-raised",
          tooLong && "border-down focus-visible:ring-down",
        )}
        // Submitting on Enter matches every other prompt box; Shift+Enter still
        // makes a newline, which multi-part questions need.
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && submittable && !pending) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <p
          id="query-counter"
          className={cn(
            "numeric text-[11px]",
            tooLong ? "text-down" : length > QUERY_WARN_AT ? "text-primary" : "text-faint",
          )}
        >
          {length > QUERY_WARN_AT || tooLong
            ? `${length} / ${MAX_QUERY_CHARS}`
            : "Enter to send · Shift+Enter for a new line"}
        </p>

        <Button type="submit" disabled={!submittable || pending} className="gap-2 font-medium">
          {pending ? "Researching…" : "Research"}
          {!pending ? <CornerDownLeft className="h-3.5 w-3.5" aria-hidden="true" /> : null}
        </Button>
      </div>

      {showExamples && !pending ? <Examples onPick={setQuery} /> : null}
    </div>
  );
}

/**
 * Starting points, taken from the acceptance table in PROJECT_PLAN §7.
 *
 * They are ordered so that working through them shows the agent choosing
 * differently each time -- one tool, then one, then three, then none.
 */
function Examples({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="mt-6">
      <p className="text-xs text-faint">Try one of these:</p>
      <ul className="mt-2 space-y-1.5">
        {EXAMPLE_QUERIES.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onPick(example)}
              className="rounded-sm text-left text-[13px] leading-snug text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
