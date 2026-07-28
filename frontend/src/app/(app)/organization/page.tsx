import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Organization" };

/** Placeholder. Replaced by CR-24. */
export default function OrganizationPage() {
  return (
    <ComingSoon
      title="Organization"
      description="Members and invite codes."
      cr="CR-24"
      scope="The member list and invite-code generator. Admin only — the backend answers 403 to anyone else regardless of this page."
    />
  );
}
