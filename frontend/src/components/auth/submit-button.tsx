"use client";

import { Loader2 } from "lucide-react";
import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";

/**
 * Submit button wired to the enclosing form's pending state.
 *
 * `useFormStatus` reads from the nearest form, so this needs no props and no
 * lifted state -- and it cannot fall out of sync with the action it submits.
 */
export function SubmitButton({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();

  return (
    <Button type="submit" disabled={pending} className="mt-5 h-[42px] w-full font-semibold">
      {pending ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
          Working…
        </>
      ) : (
        children
      )}
    </Button>
  );
}
