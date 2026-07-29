"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const PHASES = [
  "Deciding which sources the question needs",
  "Querying the selected sources in parallel",
  "Writing the report and attributing every figure",
];

/**
 * What the agent is doing, while it does it.
 *
 * The three phases are listed as the fixed sequence they are, not animated as
 * if their transitions were observed -- the endpoint is a single request with
 * no progress channel, and a bar that advanced on a timer would be inventing
 * information. The elapsed counter is real, so the wait is at least legible.
 */
export function WorkingState() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <Card className="bg-surface">
      <CardContent className="py-8">
        <div className="flex items-center justify-center gap-3">
          <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground" role="status">
            Researching…{" "}
            <span className="numeric text-faint">{elapsed}s</span>
          </p>
        </div>

        <ol className="mx-auto mt-6 max-w-[42ch] space-y-2">
          {PHASES.map((phase) => (
            <li key={phase} className="flex gap-2.5 text-xs leading-relaxed text-faint">
              <span aria-hidden="true" className="text-primary-dim">
                ·
              </span>
              {phase}
            </li>
          ))}
        </ol>

        <p className="mt-6 text-center text-[11px] text-faint">
          This usually takes 10–30 seconds.
        </p>
      </CardContent>
    </Card>
  );
}
