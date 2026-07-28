import { Loader2 } from "lucide-react";

/**
 * The root loading boundary.
 *
 * The `(app)` layout awaits the session before it can render, and a child
 * route's own `loading.tsx` cannot appear until its parent layout has. Without
 * a fallback at this level that wait is dead time with nothing on screen --
 * which reads as "the app froze, then jumped".
 */
export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <p role="status" className="flex items-center gap-2.5 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        Loading…
      </p>
    </div>
  );
}
