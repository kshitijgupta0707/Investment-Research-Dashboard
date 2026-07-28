"use client";

import { useState } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { Check, Tag } from "lucide-react";

import { TagList } from "@/components/reports/tag-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateTags } from "@/lib/reports/actions";
import { idleTagsState, MAX_TAGS } from "@/lib/reports/schema";

interface EditTagsProps {
  reportId: string;
  tags: string[];
  /** False when the viewer is neither the author nor an admin. */
  canEdit: boolean;
  deniedReason: string | null;
}

/**
 * View and edit a report's tags.
 *
 * Read-only for anyone who cannot modify the report. Hiding the control is a
 * courtesy — the backend rejects the write with a 403 either way — but showing
 * an editor that always fails would be worse than showing none.
 */
export function EditTags({ reportId, tags, canEdit, deniedReason }: EditTagsProps) {
  const [state, formAction] = useFormState(updateTags, idleTagsState);
  const [editing, setEditing] = useState(false);

  const current = state.status === "saved" ? state.tags : tags;

  if (!canEdit) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {current.length > 0 ? (
          <TagList tags={current} linked />
        ) : (
          <span className="text-[11px] text-faint">No tags</span>
        )}
        {deniedReason ? <span className="text-[11px] text-faint">{deniedReason}</span> : null}
      </div>
    );
  }

  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {current.length > 0 ? (
          <TagList tags={current} linked />
        ) : (
          <span className="text-[11px] text-faint">No tags</span>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setEditing(true)}
          className="h-6 gap-1.5 px-2 text-[11px] text-muted-foreground"
        >
          <Tag className="h-3 w-3" aria-hidden="true" />
          Edit tags
        </Button>
        {state.status === "saved" ? (
          <span className="flex items-center gap-1 text-[11px] text-up">
            <Check className="h-3 w-3" aria-hidden="true" />
            Saved
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <form
      action={(formData) => {
        formAction(formData);
        setEditing(false);
      }}
      className="flex flex-wrap items-center gap-2"
    >
      <input type="hidden" name="id" value={reportId} />
      <Input
        name="tags"
        defaultValue={current.join(", ")}
        autoFocus
        aria-label="Tags, comma separated"
        placeholder={`Up to ${MAX_TAGS}, comma separated`}
        className="h-8 max-w-[320px] border-border bg-surface text-[12px]"
      />
      <SaveTags />
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setEditing(false)}
        className="h-8 text-[12px] text-muted-foreground"
      >
        Cancel
      </Button>

      {state.status === "error" ? (
        <p role="alert" className="w-full text-[12px] text-down">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}

function SaveTags() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="sm" disabled={pending} className="h-8 text-[12px]">
      {pending ? "Saving…" : "Save"}
    </Button>
  );
}
