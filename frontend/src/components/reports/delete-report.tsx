"use client";

import { useFormState, useFormStatus } from "react-dom";
import { Trash2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { deleteReport } from "@/lib/reports/actions";
import { idleTagsState } from "@/lib/reports/schema";

/**
 * Delete, behind a confirmation.
 *
 * Deletion is not recoverable and the report is shared with the whole
 * workspace, so it asks first and names what is being removed. On success the
 * action redirects to the list; there would be nothing left to render here.
 */
export function DeleteReport({ reportId, queryText }: { reportId: string; queryText: string }) {
  const [state, formAction] = useFormState(deleteReport, idleTagsState);

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 text-[12px] text-muted-foreground hover:text-down"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          Delete
        </Button>
      </AlertDialogTrigger>

      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this report?</AlertDialogTitle>
          <AlertDialogDescription className="space-y-2">
            <span className="block">
              &ldquo;{queryText}&rdquo; will be removed for everyone in the workspace. This
              cannot be undone.
            </span>
            <span className="block text-faint">
              The query stays in your history, so you can run it again.
            </span>
          </AlertDialogDescription>
        </AlertDialogHeader>

        {state.status === "error" ? (
          <p role="alert" className="text-[12.5px] text-down">
            {state.message}
          </p>
        ) : null}

        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <form action={formAction}>
            <input type="hidden" name="id" value={reportId} />
            <ConfirmDelete />
          </form>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ConfirmDelete() {
  const { pending } = useFormStatus();

  return (
    <AlertDialogAction
      type="submit"
      disabled={pending}
      className="bg-down text-background hover:bg-down/90"
    >
      {pending ? "Deleting…" : "Delete report"}
    </AlertDialogAction>
  );
}
