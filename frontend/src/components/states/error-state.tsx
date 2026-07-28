"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { AlertTriangle, Loader2, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  /** What failed, in the user's terms. */
  title?: string;
  /** The backend's own message, when there is one worth showing. */
  detail?: string;
  /** Whether the failure is worth trying again — most are. */
  retryable?: boolean;
  /** Compact form, for a panel inside a page rather than the whole page. */
  inline?: boolean;
  className?: string;
}

/**
 * A failed fetch, shown where the data would have been.
 *
 * Retry is `router.refresh()`, which re-runs the server render for the current
 * route without a full page load — so one panel recovering does not discard
 * everything else on screen, and any form state the user has typed survives.
 *
 * Used for every read failure in the app, so a rate-limited endpoint and an
 * unreachable backend look and behave the same wherever they happen.
 */
export function ErrorState({
  title = "This could not be loaded",
  detail,
  retryable = true,
  inline = false,
  className,
}: ErrorStateProps) {
  const router = useRouter();
  const [retrying, startTransition] = useTransition();

  return (
    <div
      className={cn(
        "flex flex-col items-center text-center",
        inline ? "px-4 py-8" : "rounded-lg border border-dashed border-border px-4 py-12",
        className,
      )}
    >
      <AlertTriangle className="h-5 w-5 text-down" aria-hidden="true" />
      <p className="mt-3 text-sm text-muted-foreground">{title}</p>

      {detail ? (
        <p className="mt-1.5 max-w-[46ch] text-xs leading-relaxed text-faint">{detail}</p>
      ) : null}

      {retryable ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={retrying}
          onClick={() => startTransition(() => router.refresh())}
          className="mt-4 h-7 gap-1.5 px-2 text-[11px] text-primary"
        >
          {retrying ? (
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
          ) : (
            <RotateCw className="h-3 w-3" aria-hidden="true" />
          )}
          {retrying ? "Retrying…" : "Try again"}
        </Button>
      ) : null}
    </div>
  );
}
