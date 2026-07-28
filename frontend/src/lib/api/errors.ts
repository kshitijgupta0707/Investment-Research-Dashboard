import type { ApiErrorBody } from "./types";

/**
 * A failed API call, carrying the backend's machine-readable `code` rather than
 * just a status number. Callers branch on `code`; `message` is for display and
 * may change.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, body: ApiErrorBody | null, requestId: string | null = null) {
    super(body?.message ?? "The request failed.");
    this.name = "ApiError";
    this.status = status;
    this.code = body?.code ?? "UNKNOWN";
    this.requestId = requestId;
  }

  /** Authenticated, but not provisioned into an organization yet. */
  get needsOrganization(): boolean {
    return this.status === 403 && this.code === "FORBIDDEN";
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }
}

/**
 * What to show a user for a thrown error.
 *
 * An `ApiError` message is written for humans by the backend, so it passes
 * through. Anything else is a network or programming fault whose message would
 * only confuse, so it gets a generic line.
 */
export function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) {
    return "Could not reach the server. Check that the backend is running.";
  }
  return "Something went wrong. Please try again.";
}
