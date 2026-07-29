import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";

import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

/*
 * Three faces, each with a job: Archivo for prose, Space Grotesk for display,
 * IBM Plex Mono for anything numeric. Loaded through `next/font` so they are
 * self-hosted and preloaded -- no render-blocking request to a font CDN, and no
 * layout shift as they swap in.
 */
const sans = Archivo({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600"],
  display: "swap",
});

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "700"],
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FinLens.ai",
    template: "%s · FinLens.ai",
  },
  description: "AI-assisted, source-attributed equity research for analyst teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // `suppressHydrationWarning` is required by next-themes: it sets the theme
    // class on this element before React hydrates, so the server's markup and
    // the browser's deliberately disagree on exactly one attribute.
    <html lang="en" suppressHydrationWarning>
      <body className={`${sans.variable} ${display.variable} ${mono.variable} font-sans`}>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
