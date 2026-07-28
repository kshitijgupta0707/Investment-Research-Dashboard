"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Copy an invite code to the clipboard.
 *
 * The code is also rendered as selectable text beside this, so the feature
 * degrades to "read it and type it" wherever the Clipboard API is unavailable
 * -- it needs a secure context, and this app is served over plain HTTP in
 * development.
 */
export function CopyCode({ code, className }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // No clipboard permission, or an insecure context. The code is on screen
      // either way, so there is nothing useful to report.
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={copy}
      className={cn("h-7 gap-1.5 px-2 text-[11px] text-muted-foreground", className)}
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-up" aria-hidden="true" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" aria-hidden="true" />
          Copy
        </>
      )}
      <span className="sr-only">invite code {code}</span>
    </Button>
  );
}
