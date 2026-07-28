"use client";

import type { SignupIntent } from "@/lib/auth/schema";
import { cn } from "@/lib/utils";

interface WorkspaceChoiceProps {
  value: SignupIntent;
  onChange: (intent: SignupIntent) => void;
}

const OPTIONS: ReadonlyArray<{ value: SignupIntent; title: string; detail: string }> = [
  { value: "create", title: "New workspace", detail: "For a firm not here yet" },
  { value: "join", title: "Join with a code", detail: "Sent to you by an admin" },
];

/**
 * Create-a-workspace versus join-an-existing-one.
 *
 * Real buttons with `aria-pressed` rather than styled radios: they carry a
 * title and a description, which a radio's label would have to flatten.
 */
export function WorkspaceChoice({ value, onChange }: WorkspaceChoiceProps) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-2.5" role="group" aria-label="Workspace">
      {OPTIONS.map((option) => {
        const selected = option.value === value;

        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-md border p-3 text-left transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              selected
                ? "border-primary bg-surface-raised ring-[3px] ring-primary/10"
                : "border-border bg-surface hover:border-primary-dim",
            )}
          >
            <span className="block text-[13px] font-semibold">{option.title}</span>
            <span
              className={cn(
                "mt-0.5 block text-[11.5px] leading-snug",
                selected ? "text-muted-foreground" : "text-faint",
              )}
            >
              {option.detail}
            </span>
          </button>
        );
      })}
    </div>
  );
}
