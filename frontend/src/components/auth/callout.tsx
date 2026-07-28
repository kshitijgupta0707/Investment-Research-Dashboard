import { cn } from "@/lib/utils";

type Tone = "info" | "error";

interface CalloutProps {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}

const tones: Record<Tone, string> = {
  info: "border-primary-dim bg-primary/5 text-muted-foreground",
  error: "border-down bg-down/[0.07] text-down",
};

/**
 * A bordered aside: what a role grants, or why a submission failed.
 *
 * Errors announce themselves politely so a screen reader hears the reason
 * without losing the user's place in the form.
 */
export function Callout({ tone = "info", children, className }: CalloutProps) {
  return (
    <p
      role={tone === "error" ? "alert" : undefined}
      className={cn(
        "mt-3 border-l-2 px-3 py-2.5 text-[12.5px] leading-relaxed",
        tones[tone],
        className,
      )}
    >
      {children}
    </p>
  );
}
