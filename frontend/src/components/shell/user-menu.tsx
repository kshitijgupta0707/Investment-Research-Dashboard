import { Building2, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { CurrentUser } from "@/lib/api/types";
import { logout } from "@/lib/auth/actions";
import { cn } from "@/lib/utils";

interface UserMenuProps {
  user: CurrentUser;
  /** The organization this session belongs to. Null if it could not be read. */
  orgName?: string | null;
}

/**
 * Which workspace, who is signed in, and the way out.
 *
 * One row below `md`, a stacked block above it; the address drops on narrow
 * screens. Sign-out posts to a server action so it clears the cookie
 * server-side and works without JavaScript.
 */
export function UserMenu({ user, orgName }: UserMenuProps) {
  return (
    <div className="flex items-center gap-2 border-t border-hairline pt-3 md:flex-col md:items-stretch md:gap-0">
      {orgName ? (
        <div className="flex min-w-0 max-w-fit items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5 md:mb-2.5 md:max-w-none md:py-2">
          <Building2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
          <span className="truncate text-[12.5px] font-medium" title={orgName}>
            {orgName}
          </span>
        </div>
      ) : null}

      <div className="ml-auto flex shrink-0 items-center gap-2 md:ml-0 md:w-full md:justify-between md:px-3 md:pb-2">
        <p
          className="hidden truncate text-[12px] text-muted-foreground md:block"
          title={user.email}
        >
          {user.email}
        </p>
        {/* Admin takes the accent because it is the role that unlocks things;
            analyst stays neutral so the difference is visible at a glance. */}
        <span
          className={cn(
            "numeric shrink-0 rounded-sm border px-1.5 py-0.5 text-[9.5px] uppercase tracking-wider",
            user.role === "admin"
              ? "border-primary/35 bg-primary/[0.08] text-primary"
              : "border-border text-faint",
          )}
        >
          {user.role}
        </span>
      </div>

      <form action={logout} className="shrink-0 md:w-full">
        <Button
          type="submit"
          variant="ghost"
          size="sm"
          aria-label="Sign out"
          className="h-8 w-8 justify-center p-0 text-muted-foreground hover:text-foreground md:h-9 md:w-full md:justify-start md:gap-3 md:px-3"
        >
          <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="hidden md:inline">Sign out</span>
        </Button>
      </form>
    </div>
  );
}
