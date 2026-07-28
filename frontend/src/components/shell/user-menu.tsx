import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { CurrentUser } from "@/lib/api/types";
import { logout } from "@/lib/auth/actions";

/**
 * Who is signed in, and the way out.
 *
 * Sign-out is a form posting to a server action rather than a click handler, so
 * it clears the session cookie server-side and works without JavaScript.
 */
export function UserMenu({ user }: { user: CurrentUser }) {
  return (
    <div className="border-t border-hairline pt-3">
      <div className="px-3 pb-2">
        <p className="truncate text-[13px] font-medium">{user.email}</p>
        <p className="numeric text-[10.5px] uppercase tracking-wider text-faint">{user.role}</p>
      </div>

      <form action={logout}>
        <Button
          type="submit"
          variant="ghost"
          className="w-full justify-start gap-3 px-3 text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sign out
        </Button>
      </form>
    </div>
  );
}
