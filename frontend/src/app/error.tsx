"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/**
 * The last line of defence.
 *
 * Without this, a throw during server rendering leaves a blank document and the
 * only clue is in the terminal. The message is shown rather than hidden: this
 * is a tool for analysts running it locally, not a public site where an
 * internal detail would be a leak.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-[460px]">
        <p className="numeric text-[10.5px] uppercase tracking-[0.13em] text-down">
          Something broke
        </p>

        <h1 className="mb-2 mt-3 font-display text-2xl font-medium tracking-[-0.025em]">
          This page could not be loaded
        </h1>

        <p className="text-sm leading-relaxed text-muted-foreground">
          The most common cause is the API not running. Check that the backend is up on{" "}
          <code className="numeric text-foreground">localhost:8000</code>.
        </p>

        <pre className="numeric mt-4 max-h-40 overflow-auto whitespace-pre-wrap break-words border-l-2 border-down bg-down/[0.07] px-3 py-2.5 text-[12px] leading-relaxed text-down">
          {error.message}
        </pre>

        <Button onClick={reset} className="mt-6 h-[42px] w-full font-semibold">
          Try again
        </Button>
      </div>
    </main>
  );
}
