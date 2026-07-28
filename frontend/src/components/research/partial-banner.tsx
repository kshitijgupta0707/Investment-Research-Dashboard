import { AlertTriangle } from "lucide-react";

import { toolMeta } from "@/lib/tools";

/**
 * Says which sources failed, when any did.
 *
 * `partial` is set by the backend from what actually happened, never by the
 * model — so this is a statement about the run, not the report's own claim
 * about itself. Naming the failed tools matters: "some data is missing" is not
 * actionable, "the news source timed out" tells the analyst what to discount.
 */
export function PartialBanner({ failedTools }: { failedTools: string[] }) {
  if (failedTools.length === 0) return null;

  const names = failedTools.map((tool) => toolMeta(tool).label);
  const list =
    names.length === 1
      ? names[0]
      : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

  return (
    <div
      role="status"
      className="flex items-start gap-3 border-l-2 border-primary bg-primary/[0.06] px-4 py-3"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      <p className="text-[13px] leading-relaxed text-muted-foreground">
        <span className="font-medium text-foreground">Partial result.</span> {list} did not
        respond, so this report was written without {names.length === 1 ? "it" : "them"}. The
        rest of the sources answered.
      </p>
    </div>
  );
}
