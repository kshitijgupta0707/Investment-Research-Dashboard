export type InviteState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "created"; code: string }
  | { status: "revoked" };

export const idleInviteState: InviteState = { status: "idle" };
