import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";
import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

/**
 * The 404.
 *
 * Next's built-in fallback styles its text black inline, which on this theme's
 * near-black background renders as an apparently empty page with no way out.
 * This one inherits the theme and always offers a route back.
 */
export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-[420px]">
        <BrandMark />

        <p className="numeric mt-8 text-[10.5px] uppercase tracking-[0.13em] text-primary-dim">
          404
        </p>

        <h1 className="mb-2 mt-3 font-display text-2xl font-medium tracking-[-0.025em]">
          There&apos;s nothing at this address
        </h1>

        <p className="text-sm leading-relaxed text-muted-foreground">
          The link may be out of date, or the page may not be built yet.
        </p>

        <Button asChild className="mt-6 h-[42px] w-full font-semibold">
          <Link href={routes.dashboard}>Back to dashboard</Link>
        </Button>
      </div>
    </main>
  );
}
