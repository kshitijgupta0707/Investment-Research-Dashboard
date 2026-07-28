import type { CurrentUser, ReportSummary } from "@/lib/api/types";

/**
 * Whether this user may edit or delete this report.
 *
 * Mirrors `require_owner_or_admin` in the backend. **This is presentation
 * only.** The API re-checks the same rule on every write and answers 403
 * regardless of what the UI rendered — hiding a button is a courtesy to the
 * user, not a control. Duplicating the rule here would be dangerous if it were
 * the only place it lived; it is not.
 */
export function canModify(report: ReportSummary, user: CurrentUser): boolean {
  return user.role === "admin" || report.created_by === user.id;
}

/** Why the actions are unavailable, when they are. */
export function modifyDeniedReason(report: ReportSummary, user: CurrentUser): string | null {
  if (canModify(report, user)) return null;
  return `Only ${report.created_by_email} or an admin can change this report.`;
}
