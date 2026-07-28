/** Display formatting, in one place so no two screens disagree. */

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const ABSOLUTE = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;

/**
 * "3 hours ago", "yesterday".
 *
 * Takes `now` as an argument rather than reading the clock, so a server render
 * and its hydration agree on the answer. Callers on the server pass a value
 * captured once for the whole page.
 */
export function relativeTime(iso: string, now: number): string {
  const elapsed = new Date(iso).getTime() - now;
  const magnitude = Math.abs(elapsed);

  if (magnitude < MINUTE) return "just now";
  if (magnitude < HOUR) return RELATIVE.format(Math.round(elapsed / MINUTE), "minute");
  if (magnitude < DAY) return RELATIVE.format(Math.round(elapsed / HOUR), "hour");
  if (magnitude < WEEK) return RELATIVE.format(Math.round(elapsed / DAY), "day");
  return RELATIVE.format(Math.round(elapsed / WEEK), "week");
}

/** The full timestamp, for a `title` attribute beside the relative one. */
export function absoluteTime(iso: string): string {
  return ABSOLUTE.format(new Date(iso));
}

/**
 * A report is a frozen snapshot; past a day old, its figures may have moved.
 * PROJECT_PLAN §3.10 asks for this to be visible rather than implied.
 */
export function isStale(iso: string, now: number): boolean {
  return now - new Date(iso).getTime() > DAY;
}

export function seconds(ms: number | null): string | null {
  return ms === null ? null : `${(ms / 1000).toFixed(1)}s`;
}

/** Trim a long query to a readable line without cutting mid-word. */
export function truncate(text: string, max = 90): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > max * 0.6 ? lastSpace : max).trimEnd()}…`;
}
