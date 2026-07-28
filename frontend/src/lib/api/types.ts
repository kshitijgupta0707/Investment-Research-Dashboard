/**
 * The backend contract, mirrored.
 *
 * These types are hand-maintained against `backend/app/schemas/`. They are the
 * only place the frontend describes the API's shape -- no component declares
 * its own version of a report or a user.
 */

export type Role = "admin" | "analyst";

/** Every endpoint returns this envelope, for success and failure alike. */
export interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: ApiErrorBody | null;
  meta: { request_id: string | null; timestamp: string };
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown[] | null;
}

/** `GET /api/me` -- the caller's identity, organization and role. */
export interface CurrentUser {
  id: string;
  auth_id: string;
  email: string;
  org_id: string;
  role: Role;
}

/** What `POST /api/org` and `POST /api/org/join` return. */
export interface Membership {
  user_id: string;
  org_id: string;
  org_name: string;
  role: Role;
}

export interface Organization {
  id: string;
  name: string;
  member_count: number;
  created_at: string;
}
