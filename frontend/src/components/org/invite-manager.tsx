"use client";

import { useFormState, useFormStatus } from "react-dom";
import { Plus } from "lucide-react";

import { CopyCode } from "@/components/org/copy-code";
import { Button } from "@/components/ui/button";
import type { Invite } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";
import { createInvite, revokeInvite } from "@/lib/org/actions";
import { idleInviteState } from "@/lib/org/schema";
import { cn } from "@/lib/utils";

/**
 * Generate and revoke invite codes.
 *
 * One shared code per invite rather than a per-person invitation -- the plan
 * descopes per-email invites (§11). Anyone holding a live code joins as an
 * analyst, which is why revoking matters and why codes expire.
 */
export function InviteManager({ invites }: { invites: Invite[] }) {
  const [state, formAction] = useFormState(createInvite, idleInviteState);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-muted-foreground">
          Share a code with a colleague — they join as an analyst.
        </p>
        <form action={formAction}>
          <GenerateButton />
        </form>
      </div>

      {state.status === "error" ? (
        <p role="alert" className="border-l-2 border-down bg-down/[0.07] px-3 py-2 text-[12.5px] text-down">
          {state.message}
        </p>
      ) : null}

      {invites.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-4 py-6 text-center text-[12px] text-faint">
          No invite codes yet. Generate one to add a colleague.
        </p>
      ) : (
        <ul className="divide-y divide-hairline rounded-lg border border-border">
          {invites.map((invite) => (
            <InviteRow key={invite.id} invite={invite} />
          ))}
        </ul>
      )}
    </div>
  );
}

function InviteRow({ invite }: { invite: Invite }) {
  const [state, formAction] = useFormState(revokeInvite, idleInviteState);

  // `status` alone is not enough: nothing sweeps the table, so a lapsed invite
  // is still stored "active". The backend derives `expired` from the timestamp.
  const usable = invite.status === "active" && !invite.expired;

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
      <code
        className={cn(
          "numeric select-all text-sm tracking-[0.15em]",
          usable ? "text-foreground" : "text-faint line-through",
        )}
      >
        {invite.code}
      </code>

      <StatusLabel invite={invite} usable={usable} />

      <span className="numeric ml-auto text-[10px] text-faint">
        by {invite.created_by_email}
      </span>

      {usable ? (
        <>
          <CopyCode code={invite.code} />
          <form action={formAction}>
            <input type="hidden" name="id" value={invite.id} />
            <RevokeButton />
          </form>
        </>
      ) : null}

      {state.status === "error" ? (
        <p role="alert" className="w-full text-[11px] text-down">
          {state.message}
        </p>
      ) : null}
    </li>
  );
}

function StatusLabel({ invite, usable }: { invite: Invite; usable: boolean }) {
  if (invite.status === "revoked") {
    return <Badge tone="muted">revoked</Badge>;
  }
  if (invite.expired) {
    return <Badge tone="muted">expired</Badge>;
  }
  return (
    <span className="numeric text-[10px] text-faint">
      {usable && invite.expires_at
        ? `expires ${absoluteTime(invite.expires_at).split(",")[0]}`
        : "no expiry"}
    </span>
  );
}

function Badge({ tone, children }: { tone: "muted"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "numeric rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-wider",
        tone === "muted" && "border-border bg-surface text-faint",
      )}
    >
      {children}
    </span>
  );
}

function GenerateButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="sm" disabled={pending} className="gap-1.5">
      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
      {pending ? "Generating…" : "Generate code"}
    </Button>
  );
}

function RevokeButton() {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      variant="ghost"
      size="sm"
      disabled={pending}
      className="h-7 px-2 text-[11px] text-muted-foreground hover:text-down"
    >
      {pending ? "Revoking…" : "Revoke"}
    </Button>
  );
}
