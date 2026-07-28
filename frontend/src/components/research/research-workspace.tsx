"use client";

import { useFormState, useFormStatus } from "react-dom";

import { ReportView } from "@/components/report/report-view";
import { ToolBadges } from "@/components/research/tool-badges";
import { Card, CardContent } from "@/components/ui/card";
import { runQuery } from "@/lib/research/actions";
import { idleResearchState } from "@/lib/research/schema";
import { seconds } from "@/lib/format";

import { QueryForm } from "./query-form";
import { SaveReport } from "./save-report";
import { WorkingState } from "./working-state";

/**
 * The research page: ask, wait, read, save.
 *
 * One client component holds the whole exchange because the result has to
 * survive on screen while the form is still usable -- an analyst reads the
 * report, then refines the question without losing what they just got.
 */
export function ResearchWorkspace({ initialQuery = "" }: { initialQuery?: string }) {
  const [state, formAction] = useFormState(runQuery, idleResearchState);

  return (
    <div className="space-y-6">
      <form action={formAction}>
        <QueryForm
          // After a failure the question is handed back so it is not retyped.
          initialQuery={state.status === "error" ? state.queryText : initialQuery}
          showExamples={state.status === "idle" && !initialQuery}
        />
        <Pending />
      </form>

      {state.status === "error" ? <QueryError message={state.message} /> : null}

      {state.status === "done" ? (
        <section className="space-y-4">
          <ResultHeader
            tools={state.result.tools_selected}
            latencyMs={state.result.latency_ms}
          />
          <ReportView report={state.result.report} />
          <SaveReport result={state.result} />
        </section>
      ) : null}
    </div>
  );
}

/**
 * The working state, rendered inside the form so `useFormStatus` can see it.
 *
 * That hook reads the nearest enclosing form, so it has to be a child of the
 * form element rather than a sibling of it.
 */
function Pending() {
  const { pending } = useFormStatus();
  if (!pending) return null;

  return (
    <div className="mt-6">
      <WorkingState />
    </div>
  );
}

/**
 * What was actually consulted, and how long it took.
 *
 * Shown above every result because selective tool choice is the claim the
 * product is making -- a news-only question that visibly did not touch the
 * price feed is the proof.
 */
function ResultHeader({ tools, latencyMs }: { tools: string[]; latencyMs: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span className="numeric text-[10px] uppercase tracking-wider text-faint">
        Sources used
      </span>
      <ToolBadges tools={tools} />
      <span className="numeric text-[10px] text-faint">· {seconds(latencyMs)}</span>
    </div>
  );
}

function QueryError({ message }: { message: string }) {
  return (
    <Card className="border-down/40 bg-down/[0.05]">
      <CardContent className="py-5">
        <p role="alert" className="text-[13px] leading-relaxed text-down">
          {message}
        </p>
        <p className="mt-2 text-[12px] text-faint">
          Your question is still in the box — edit it and try again.
        </p>
      </CardContent>
    </Card>
  );
}
