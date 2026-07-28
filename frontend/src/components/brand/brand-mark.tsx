import { cn } from "@/lib/utils";

export const PRODUCT_NAME = "Meridian Research";

interface BrandMarkProps {
  className?: string;
  /** Hide the wordmark, for narrow rails. */
  glyphOnly?: boolean;
}

/** The product lockup. Defined once so the sidebar and auth panel cannot drift. */
export function BrandMark({ className, glyphOnly = false }: BrandMarkProps) {
  return (
    <span className={cn("flex items-center gap-3", className)}>
      <span
        aria-hidden="true"
        className={cn(
          "grid h-[25px] w-[25px] place-items-center border-[1.5px] border-primary",
          "text-xs text-primary shadow-[0_0_18px_hsl(var(--primary)/0.3)]",
        )}
      >
        ◧
      </span>
      {glyphOnly ? (
        <span className="sr-only">{PRODUCT_NAME}</span>
      ) : (
        <span className="font-display text-[16.5px] font-bold tracking-tight">{PRODUCT_NAME}</span>
      )}
    </span>
  );
}
