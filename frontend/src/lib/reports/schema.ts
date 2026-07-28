/** Mirrors the limits in backend/app/schemas/reports.py. */
export const MAX_TAGS = 10;
export const MAX_TAG_CHARS = 32;

export type TagsState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "saved"; tags: string[] };

export const idleTagsState: TagsState = { status: "idle" };
