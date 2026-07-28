import { ShieldCheck } from "lucide-react";

import type { Member } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Everyone in the workspace. Admins first, as the API returns them. */
export function MemberList({ members, currentUserId }: { members: Member[]; currentUserId: string }) {
  return (
    <ul className="divide-y divide-hairline rounded-lg border border-border">
      {members.map((member) => (
        <li key={member.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px]">
              {member.name ?? member.email}
              {member.id === currentUserId ? (
                <span className="ml-2 text-[11px] text-faint">you</span>
              ) : null}
            </p>
            {member.name ? (
              <p className="numeric truncate text-[11px] text-faint">{member.email}</p>
            ) : null}
          </div>

          <RoleBadge role={member.role} />

          <span className="numeric hidden shrink-0 text-[10px] text-faint sm:inline">
            joined {absoluteTime(member.created_at).split(",")[0]}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RoleBadge({ role }: { role: Member["role"] }) {
  const isAdmin = role === "admin";

  return (
    <span
      className={cn(
        "numeric inline-flex shrink-0 items-center gap-1 rounded-sm border px-1.5 py-0.5",
        "text-[10px] uppercase tracking-wider",
        isAdmin
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-border bg-surface text-muted-foreground",
      )}
      title={
        isAdmin
          ? "Can manage the workspace and modify anyone's reports"
          : "Full research access; cannot manage the workspace"
      }
    >
      {isAdmin ? <ShieldCheck className="h-2.5 w-2.5" aria-hidden="true" /> : null}
      {role}
    </span>
  );
}
