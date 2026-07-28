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

/* --- the Turn-2 report contract ------------------------------------------
 *
 * This mirrors `backend/app/schemas/report.py` and is the only agreement
 * between the agent and this UI. Nothing here parses prose: a section carries
 * its `type`, and the renderer switches on it.
 */

export type Confidence = "high" | "medium" | "low";
export type SectionType = "text" | "table" | "chart" | "company_card" | "sentiment";
export type SourceType = "api" | "article" | "filing";
export type Sentiment = "positive" | "negative" | "neutral";

/** Where one section's claims came from. Attribution is per section. */
export interface Source {
  type: SourceType;
  label: string;
  url: string | null;
  /** When the provider said its data was current. Null for filings. */
  data_as_of: string | null;
}

export interface TextContent {
  text: string;
}

export interface TableContent {
  columns: string[];
  rows: Array<Array<string | number | null>>;
}

export interface ChartPoint {
  date: string;
  value: number;
}

export interface ChartContent {
  series: Array<{ label: string; points: ChartPoint[] }>;
  y_label: string | null;
}

export interface CompanyCardContent {
  ticker: string;
  company_name: string | null;
  /** Pre-formatted for display -- "$2.1T", not 2_100_000_000_000. */
  metrics: Array<{ label: string; value: string | null }>;
}

export interface SentimentContent {
  items: Array<{
    headline: string;
    sentiment: Sentiment;
    ticker: string | null;
    url: string | null;
  }>;
  overall: Sentiment | null;
}

export type SectionContent =
  | TextContent
  | TableContent
  | ChartContent
  | CompanyCardContent
  | SentimentContent;

export interface Section {
  title: string;
  type: SectionType;
  content: SectionContent;
  confidence: Confidence;
  sources: Source[];
}

export interface ResearchReport {
  summary: string;
  sections: Section[];
  /** True when any tool failed. The backend sets this, never the model. */
  partial: boolean;
  failed_tools: string[];
  generated_at: string;
}

/** A saved report with its full structured result. */
export interface ReportDetail extends ReportSummary {
  structured_result: ResearchReport;
}

/** What `POST /api/research/query` returns: the report plus its provenance. */
export interface ResearchQueryResponse {
  query_id: string;
  query_text: string;
  tools_selected: string[];
  status: QueryStatus;
  latency_ms: number;
  report: ResearchReport;
}
