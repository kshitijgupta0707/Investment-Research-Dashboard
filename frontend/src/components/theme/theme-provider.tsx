"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";

/**
 * Theme context for the whole app.
 *
 * `disableTransitionOnChange` stops every colour animating independently as the
 * class swaps, which reads as a smear.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}
