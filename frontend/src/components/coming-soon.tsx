import { Hammer } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";

interface ComingSoonProps {
  title: string;
  description: string;
  /** The CR that replaces this placeholder, so it is obvious what is pending. */
  cr: string;
  /** What the finished page will do. */
  scope: string;
}

/**
 * A route that exists so navigation never dead-ends, but is not built yet.
 *
 * Deliberately explicit about being a placeholder rather than dressing an
 * unfinished screen up as an empty state -- an empty state means "you have no
 * data", which is a different and misleading claim.
 *
 * Every use of this is replaced by its own CR; none should survive to the demo.
 */
export function ComingSoon({ title, description, cr, scope }: ComingSoonProps) {
  return (
    <>
      <PageHeader title={title} description={description} />

      <Card className="border-dashed bg-transparent">
        <CardContent className="flex flex-col items-center py-12 text-center">
          <Hammer className="h-5 w-5 text-faint" aria-hidden="true" />
          <p className="mt-3 text-sm text-muted-foreground">Not built yet — {cr}</p>
          <p className="mt-1.5 max-w-[46ch] text-xs leading-relaxed text-faint">{scope}</p>
        </CardContent>
      </Card>
    </>
  );
}
