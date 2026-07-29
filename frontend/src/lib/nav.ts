import {
  Building2,
  FileText,
  LayoutDashboard,
  Search,
  Star,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/lib/api/types";
import { routes } from "@/lib/routes";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Roles allowed to see this item. Omit for everyone. */
  roles?: readonly Role[];
  /**
   * Moves to the header as an icon on the narrowest screens.
   *
   * Four labelled destinations do not fit legibly below 480px. Rather than let
   * them scroll out of sight -- where a destination might as well not exist --
   * the less frequently used ones become icons beside the theme toggle, and the
   * three that remain share the full width.
   */
  compact?: boolean;
}

/**
 * The sidebar, declared once.
 *
 * Hiding an item is a courtesy, not a control: the backend gates every
 * admin-only endpoint with `require_admin` and answers 403 regardless of what
 * the nav happens to render.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: routes.dashboard, label: "Dashboard", icon: LayoutDashboard },
  { href: routes.research, label: "New research", icon: Search },
  { href: routes.reports, label: "Saved reports", icon: FileText },
  { href: routes.watchlist, label: "Watchlist", icon: Star, compact: true },
  {
    href: routes.organization,
    label: "Organization",
    icon: Building2,
    roles: ["admin"],
    compact: true,
  },
];

export function navItemsFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role));
}

/** The destinations that keep their label at every width. */
export function primaryNavItems(role: Role): NavItem[] {
  return navItemsFor(role).filter((item) => !item.compact);
}

/** The ones that become header icons below `xs`. */
export function compactNavItems(role: Role): NavItem[] {
  return navItemsFor(role).filter((item) => item.compact);
}

/** Whether a nav item matches the current path, including its subpages. */
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
