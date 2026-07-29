"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Role } from "@/lib/api/types";
import { compactNavItems, isActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

/**
 * Icon links for the destinations that drop out of the nav bar below `xs`.
 *
 * Hidden from `xs` up, where `SidebarNav` shows them with labels instead.
 */
export function CompactNav({ role }: { role: Role }) {
  const pathname = usePathname();
  const items = compactNavItems(role);

  if (items.length === 0) return null;

  return (
    <nav aria-label="More" className="flex items-center gap-0.5 xs:hidden">
      {items.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);

        return (
          <Link
            key={href}
            href={href}
            aria-label={label}
            title={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "grid h-8 w-8 place-items-center rounded-md transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "border border-border/70 bg-surface-raised text-primary"
                : "text-muted-foreground hover:bg-surface-raised hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
          </Link>
        );
      })}
    </nav>
  );
}
