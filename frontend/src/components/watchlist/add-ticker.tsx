"use client";

import { useEffect, useRef } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { addTicker } from "@/lib/watchlist/actions";
import { idleWatchlistState, MAX_TICKER_CHARS } from "@/lib/watchlist/schema";

/**
 * Pin a company.
 *
 * `company_name` is optional and typed by the user rather than looked up: the
 * watchlist is a bookmark list, and resolving a name would mean a market-data
 * call against a rate-limited free tier just to render a label.
 */
export function AddTicker() {
  const [state, formAction] = useFormState(addTicker, idleWatchlistState);
  const formRef = useRef<HTMLFormElement>(null);

  // Clear the fields once an add succeeds, so the next one can be typed
  // straight away.
  useEffect(() => {
    if (state.status === "added") formRef.current?.reset();
  }, [state]);

  return (
    <form ref={formRef} action={formAction} className="flex flex-wrap items-end gap-2">
      <div>
        <label htmlFor="ticker" className="mb-1.5 block text-[11px] text-muted-foreground">
          Ticker
        </label>
        <Input
          id="ticker"
          name="ticker"
          required
          maxLength={MAX_TICKER_CHARS}
          placeholder="NVDA"
          autoComplete="off"
          className="numeric h-9 w-[110px] border-border bg-surface uppercase tracking-wider"
        />
      </div>

      <div className="min-w-[180px] flex-1">
        <label htmlFor="company_name" className="mb-1.5 block text-[11px] text-muted-foreground">
          Company name <span className="text-faint">(optional)</span>
        </label>
        <Input
          id="company_name"
          name="company_name"
          placeholder="NVIDIA Corporation"
          autoComplete="off"
          className="h-9 border-border bg-surface text-[13px]"
        />
      </div>

      <AddButton />

      {state.status === "error" ? (
        <p role="alert" className="w-full text-[12px] text-down">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}

function AddButton() {
  const { pending } = useFormStatus();

  return (
    <Button type="submit" size="sm" disabled={pending} className="h-9 gap-1.5">
      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
      {pending ? "Adding…" : "Add"}
    </Button>
  );
}
