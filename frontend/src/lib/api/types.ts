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

/** A paginated list. `total` is the count before the limit was applied. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** The three tools the agent may choose between, as the backend names them. */
export const TOOL = {
  marketData: "get_market_data",
  newsSentiment: "get_news_sentiment",
  knowledgeBase: "search_knowledge_base",
} as const;

export type ToolName = (typeof TOOL)[keyof typeof TOOL];

export type QueryStatus = "success" | "partial" | "failed";

/**
 * One past query, saved or not.
 *
 * `tools_selected` is the visible evidence that the agent chooses per query --
 * two adjacent rows showing different tool sets is the whole claim, in the UI.
 */
export interface QueryHistoryEntry {
  id: string;
  query_text: string;
  tools_selected: string[];
  status: QueryStatus;
  latency_ms: number | null;
  created_at: string;
}

/** A saved report in list form. Deliberately without `structured_result`. */
export interface ReportSummary {
  id: string;
  query_text: string;
  tags: string[];
  created_by: string;
  created_by_email: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string | null;
  created_at: string;
}
