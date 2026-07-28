import type { Metadata } from "next";
import { Lock } from "lucide-react";

import { InviteManager } from "@/components/org/invite-manager";
import { MemberList } from "@/components/org/member-list";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, messageFor } from "@/lib/api/errors";
import { getInvites, getMembers, getOrganization } from "@/lib/api/resources";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Organization" };

/**
 * Workspace management. Admin only.
 *
 * The sidebar hides this from analysts, but that is presentation. An analyst
 * who navigates here directly still reaches the page — and the API answers 403
 * to `/api/org/members` and `/api/org/invites` regardless. That 403 is caught
 * and explained below rather than crashing, which is exactly the demo the
 * brief asks for: the backend is the enforcement layer, not the nav.
 */
export default async function OrganizationPage() {
  const user = await getCurrentUser();

  let organization;
  let members;
  let invites;

  try {
    [organization, members, invites] = await Promise.all([
      getOrganization(),
      getMembers(),
      getInvites(),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <AdminOnly />;
    }
    return (
      <>
        <PageHeader title="Organization" description="Members and invite codes." />
        <p className="text-sm text-down">{messageFor(error)}</p>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={organization.name}
        description={`${organization.member_count} ${
          organization.member_count === 1 ? "member" : "members"
        } · everyone here shares the same saved reports.`}
      />

      <div className="space-y-6">
        <Card className="bg-surface/40">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Members</CardTitle>
          </CardHeader>
          <CardContent>
            <MemberList members={members} currentUserId={user?.id ?? ""} />
          </CardContent>
        </Card>

        <Card className="bg-surface/40">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Invite codes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <InviteManager invites={invites} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

/**
 * What an analyst sees here.
 *
 * Says plainly that the server refused, rather than pretending the page is
 * empty — the refusal is the correct behaviour and worth showing.
 */
function AdminOnly() {
  return (
    <>
      <PageHeader title="Organization" description="Members and invite codes." />

      <Card className="border-dashed bg-transparent">
        <CardContent className="flex flex-col items-center py-12 text-center">
          <Lock className="h-5 w-5 text-faint" aria-hidden="true" />
          <p className="mt-3 text-sm text-muted-foreground">This page is for admins</p>
          <p className="mt-1.5 max-w-[46ch] text-xs leading-relaxed text-faint">
            The server refused the request with a 403. Ask an admin in your workspace if you
            need an invite code or a change to members.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
