import { cn } from "@/lib/utils";

export const PRODUCT_NAME = "FinLens.ai";

/**
 * The glyph: an aperture ring with a price line drawn through it.
 *
 * Built from geometry rather than an image file so it inherits `currentColor`
 * and stays crisp at any size -- the ring reads as structure, the line and its
 * marker carry the accent. Nothing here is theme-specific; both palettes
 * resolve the same two tokens.
 */
function LensGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={cn("h-[26px] w-[26px]", className)}
    >
      {/* The lens barrel. */}
      <circle
        cx="12"
        cy="12"
        r="9.25"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeOpacity="0.32"
      />
      {/* Inner ring, tighter and fainter -- gives the mark depth at 26px
          without adding a second colour. */}
      <circle
        cx="12"
        cy="12"
        r="5.75"
        stroke="currentColor"
        strokeWidth="1"
        strokeOpacity="0.14"
      />
      {/* The reading itself. Every point sits inside the outer ring, so the
          line never appears clipped. */}
      <path
        d="M6.5 15.5 L10 11.75 L13 13.75 L17.5 8.5"
        stroke="hsl(var(--primary))"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="17.5" cy="8.5" r="1.75" fill="hsl(var(--primary))" />
    </svg>
  );
}

interface BrandMarkProps {
  className?: string;
  /** Hide the wordmark, for narrow rails. */
  glyphOnly?: boolean;
  /** Larger lockup, for the auth panel where the mark is the focal point. */
  size?: "default" | "lg";
}

/** The product lockup. Defined once so the sidebar and auth panel cannot drift. */
export function BrandMark({ className, glyphOnly = false, size = "default" }: BrandMarkProps) {
  const large = size === "lg";

  return (
    <span className={cn("group/brand flex items-center gap-2.5", className)}>
      <LensGlyph
        className={cn(
          "shrink-0 text-foreground transition-transform duration-500 ease-out",
          "group-hover/brand:rotate-[18deg]",
          large ? "h-9 w-9" : "h-[26px] w-[26px]",
        )}
      />

      {glyphOnly ? (
        <span className="sr-only">{PRODUCT_NAME}</span>
      ) : (
        <span
          className={cn(
            "text-gradient-brand font-display font-bold tracking-[-0.02em]",
            large ? "text-[24px]" : "text-[17px]",
          )}
        >
          {PRODUCT_NAME}
        </span>
      )}
    </span>
  );
}
