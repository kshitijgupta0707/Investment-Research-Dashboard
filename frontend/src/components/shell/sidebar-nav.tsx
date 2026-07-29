"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";

import type { Role } from "@/lib/api/types";
import { isActive, navItemsFor, primaryNavItems } from "@/lib/nav";
import { cn } from "@/lib/utils";

/**
 * The primary navigation. Client-side only to know which route is current.
 *
 * A row of pills below `md`, a vertical rail above it. The active highlight is
 * shared across items via `layoutId` so it slides between routes.
 */
export function SidebarNav({ role }: { role: Role }) {
  const pathname = usePathname();

  // Below `xs` the compact items move to the header; the rest split the width.
  const all = navItemsFor(role);
  const primaryCount = primaryNavItems(role).length;

  return (
    <nav
      aria-label="Primary"
      className={cn(
        "flex gap-1 pb-1",
        "xs:overflow-x-auto",
        // Scrollbar hidden on the bar layout.
        "[-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        "md:flex-col md:gap-0.5 md:overflow-visible md:pb-0",
      )}
    >
      {all.map(({ href, label, icon: Icon, compact }) => {
        const active = isActive(pathname, href);

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "xs:shrink-0 md:gap-3 md:px-3 md:py-2 md:text-sm",
              // Below `xs`: in the header instead, or an equal share of the row.
              compact
                ? "hidden xs:flex"
                : primaryCount === 3
                  ? "flex-1 justify-center gap-1.5 px-1 text-[11.5px] xs:flex-none xs:justify-start xs:gap-2 xs:px-2.5 xs:text-[13px]"
                  : "flex-1 justify-center xs:flex-none xs:justify-start",
              active
                ? "font-medium text-foreground"
                : "text-muted-foreground transition-colors hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId="nav-active"
                aria-hidden="true"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
                className="absolute inset-0 rounded-md border border-border/70 bg-surface-raised"
              >
                {/* Accent rail: under the pill on the bar, beside it on the rail. */}
                <span className="absolute inset-x-2 bottom-0 h-[2px] rounded-full bg-primary md:inset-x-auto md:bottom-auto md:left-0 md:top-1/2 md:h-4 md:w-[2px] md:-translate-y-1/2" />
              </motion.span>
            ) : (
              <span
                aria-hidden="true"
                className="absolute inset-0 rounded-md bg-surface opacity-0 transition-opacity group-hover:opacity-100"
              />
            )}

            <Icon
              className={cn(
                "relative z-10 h-4 w-4 shrink-0 transition-colors",
                active ? "text-primary" : "text-faint group-hover:text-muted-foreground",
              )}
              aria-hidden="true"
            />
            <span className="relative z-10 whitespace-nowrap md:truncate">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
