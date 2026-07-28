"use client";

import Link from "next/link";
import { useFormState, useFormStatus } from "react-dom";
import { Check, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ResearchQueryResponse } from "@/lib/api/types";
import { saveReport } from "@/lib/research/actions";
import { idleSaveState } from "@/lib/research/schema";
import { routes } from "@/lib/routes";

/**
 * Keep this result as a report.
 *
 * The structured result is posted back verbatim. A report is a frozen snapshot
 * of what the agent returned, so it cannot be rebuilt later by re-running the
 * query -- the figures would have moved.
 */
export function SaveReport({ result }: { result: ResearchQueryResponse }) {
  const [state, formAction] = useFormState(saveReport, idleSaveState);

  if (state.status === "saved") {
    return (
      <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Check className="h-4 w-4 text-up" aria-hidden="true" />
        Saved.{" "}
        <Link
          href={`${routes.reports}/${state.reportId}`}
          className="font-medium text-primary underline underline-offset-[3px]"
        >
          Open the report
        </Link>
      </p>
    );
  }

  return (
    <form action={formAction} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="payload" value={JSON.stringify(result.report)} />
      <input type="hidden" name="query_text" value={result.query_text} />

      <Input
        name="tags"
        placeholder="Tags, comma separated"
        aria-label="Tags"
        className="h-9 max-w-[240px] border-border bg-surface text-[13px]"
      />
      <SaveButton />

      {state.status === "error" ? (
        <p role="alert" className="text-[12.5px] text-down">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}

function SaveButton() {
  const { pending } = useFormStatus();

  return (
    <Button type="submit" variant="secondary" size="sm" disabled={pending} className="gap-2">
      <Save className="h-3.5 w-3.5" aria-hidden="true" />
      {pending ? "Saving…" : "Save report"}
    </Button>
  );
}
