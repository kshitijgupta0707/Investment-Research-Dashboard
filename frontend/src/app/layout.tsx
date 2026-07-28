import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono, Space_Grotesk } from "next/font/google";

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
    default: "Meridian Research",
    template: "%s · Meridian Research",
  },
  description: "AI-assisted, source-attributed equity research for analyst teams.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The product is dark-only for now; the class makes that explicit so
    // shadcn's `dark:` variants resolve rather than depending on system taste.
    <html lang="en" className="dark">
      <body className={`${sans.variable} ${display.variable} ${mono.variable} font-sans`}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
