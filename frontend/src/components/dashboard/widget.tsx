import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface WidgetProps {
  title: string;
  /** "View all" target, shown only when there is something to view. */
  href?: string;
  linkLabel?: string;
  children: React.ReactNode;
  className?: string;
}

/** The frame every dashboard panel sits in: title, optional link, body. */
export function Widget({ title, href, linkLabel = "View all", children, className }: WidgetProps) {
  return (
    <Card className={cn("bg-surface/40", className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {href ? (
          <Link
            href={href}
            className="flex items-center gap-1 rounded-sm text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {linkLabel}
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        ) : null}
      </CardHeader>
      <CardContent className="pt-0">{children}</CardContent>
    </Card>
  );
}

/**
 * What a widget shows while its data is in flight.
 *
 * Each widget streams independently, so this is what the user sees in that one
 * panel rather than the whole page being held back by the slowest endpoint.
 */
export function WidgetSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-11 w-full" />
      ))}
    </div>
  );
}
