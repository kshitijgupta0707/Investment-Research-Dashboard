"use client";

import { useState } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { NotebookPen, PenLine } from "lucide-react";

import { Prose } from "@/components/report/prose";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { updateNotes } from "@/lib/reports/actions";
import { idleNotesState, MAX_NOTES_CHARS } from "@/lib/reports/schema";
import { absoluteTime } from "@/lib/format";

interface AnalystNotesProps {
  reportId: string;
  notes: string | null;
  updatedAt: string | null;
  updatedByEmail: string | null;
  /** False when the viewer is neither the author nor an admin. */
  canEdit: boolean;
}

/**
 * An analyst's own commentary, kept beside the agent's report.
 *
 * Deliberately distinct from a generated section: the report's claim is that
 * every figure carries a source, so a person's judgement is marked as theirs
 * and never merged into `structured_result`.
 */
export function AnalystNotes({
  reportId,
  notes,
  updatedAt,
  updatedByEmail,
  canEdit,
}: AnalystNotesProps) {
  const [state, formAction] = useFormState(updateNotes, idleNotesState);
  const [editing, setEditing] = useState(false);

  // Reflect a clear immediately rather than waiting for the page to refetch.
  const current = state.status === "saved" ? (state.cleared ? null : undefined) : undefined;
  const body = current === null ? null : notes;

  if (!body && !canEdit) return null;

  if (editing) {
    return (
      <NotesCard>
        <form action={formAction} onSubmit={() => setEditing(false)}>
          <input type="hidden" name="id" value={reportId} />
          <Textarea
            name="notes"
            defaultValue={body ?? ""}
            autoFocus
            rows={5}
            maxLength={MAX_NOTES_CHARS}
            aria-label="Your note on this report"
            placeholder="What does this mean for the desk? Anything the agent missed, or a figure worth challenging."
            className="resize-y border-border bg-surface text-[13px] leading-relaxed"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SaveNotes />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setEditing(false)}
              className="h-8 text-[12px] text-muted-foreground"
            >
              Cancel
            </Button>
            <span className="text-[11px] text-faint">
              Markdown supported · clearing the box removes the note
            </span>
          </div>

          {state.status === "error" ? (
            <p role="alert" className="mt-2 text-[12px] text-down">
              {state.message}
            </p>
          ) : null}
        </form>
      </NotesCard>
    );
  }

  return (
    <NotesCard>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="numeric flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-primary">
            <NotebookPen className="h-3 w-3" aria-hidden="true" />
            Analyst note
          </p>
          {body && updatedByEmail ? (
            <p className="mt-0.5 text-[11px] text-faint">
              {updatedByEmail}
              {updatedAt ? ` · ${absoluteTime(updatedAt)}` : null}
            </p>
          ) : null}
        </div>

        {canEdit ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setEditing(true)}
            className="h-7 shrink-0 gap-1.5 px-2 text-[11px] text-muted-foreground"
          >
            <PenLine className="h-3 w-3" aria-hidden="true" />
            {body ? "Edit" : "Add a note"}
          </Button>
        ) : null}
      </div>

      {body ? (
        <div className="mt-3">
          <Prose text={body} />
        </div>
      ) : (
        <p className="mt-2 text-[12.5px] text-faint">
          Nothing added yet. Your commentary sits alongside the agent&apos;s findings, marked as
          yours.
        </p>
      )}
    </NotesCard>
  );
}

/** Dashed border and a warmer ground, so it never reads as generated output. */
function NotesCard({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-dashed border-primary/35 bg-primary/[0.035] p-4">
      {children}
    </section>
  );
}

function SaveNotes() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="sm" disabled={pending} className="h-8 text-[12px]">
      {pending ? "Saving…" : "Save note"}
    </Button>
  );
}
