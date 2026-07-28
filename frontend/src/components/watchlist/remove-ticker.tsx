"use client";

import { useFormState, useFormStatus } from "react-dom";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { removeTicker } from "@/lib/watchlist/actions";
import { idleWatchlistState } from "@/lib/watchlist/schema";

/**
 * Unpin one company.
 *
 * No confirmation: a watchlist entry holds no work, and re-adding it is two
 * keystrokes. Reserving the confirm dialog for genuinely destructive things --
 * deleting a report — keeps it meaningful.
 */
export function RemoveTicker({ id, ticker }: { id: string; ticker: string }) {
  const [state, formAction] = useFormState(removeTicker, idleWatchlistState);

  return (
    <form action={formAction} className="flex items-center gap-2">
      <input type="hidden" name="id" value={id} />
      {state.status === "error" ? (
        <span role="alert" className="text-[11px] text-down">
          {state.message}
        </span>
      ) : null}
      <RemoveButton ticker={ticker} />
    </form>
  );
}

function RemoveButton({ ticker }: { ticker: string }) {
  const { pending } = useFormStatus();

  return (
    <Button
      type="submit"
      variant="ghost"
      size="sm"
      disabled={pending}
      className="h-7 w-7 p-0 text-faint hover:text-down"
    >
      <X className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="sr-only">Remove {ticker} from your watchlist</span>
    </Button>
  );
}
