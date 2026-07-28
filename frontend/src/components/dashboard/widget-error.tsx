import { AlertTriangle } from "lucide-react";

/**
 * One widget's failure, contained.
 *
 * Each widget catches its own fetch error and renders this instead of throwing,
 * so the dashboard degrades the way the backend does: the reports endpoint
 * being down costs you the reports panel, not the page. That mirrors the
 * partial-result contract rather than contradicting it.
 */
export function WidgetError({ detail }: { detail?: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-8 text-center">
      <AlertTriangle className="h-5 w-5 text-down" aria-hidden="true" />
      <p className="mt-3 text-sm text-muted-foreground">This panel could not load.</p>
      <p className="mt-1 max-w-[38ch] text-xs leading-relaxed text-faint">
        {detail ?? "The rest of the page is unaffected."}
      </p>
    </div>
  );
}
