/**
 * Render an ISO date / datetime as the configured display format.
 * Supported tokens: DD, MM, YYYY. Default: DD-MM-YYYY.
 * Input: "YYYY-MM-DD" or full ISO datetime. Returns "" for empty input,
 * and the raw value if it cannot be parsed.
 */
export function formatDate(
  value?: string | null,
  format: string = "DD-MM-YYYY",
): string {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const [, yyyy, mm, dd] = match;
  return format.replace(/YYYY|MM|DD/g, (token) =>
    token === "YYYY" ? yyyy : token === "MM" ? mm : dd,
  );
}

/** "2026-11-15T09:30:00" or "09:30" -> "09:30" (24h). */
export function formatTime(value?: string | null): string {
  if (!value) return "";
  const match = /(\d{2}):(\d{2})/.exec(value);
  return match ? `${match[1]}:${match[2]}` : value;
}

/** ISO datetime -> DD-MM-YYYY HH:MM */
export function formatDateTime(value?: string | null, dateFormat = "DD-MM-YYYY"): string {
  if (!value) return "";
  const date = formatDate(value, dateFormat);
  const timeMatch = /T(\d{2}):(\d{2})/.exec(value);
  if (!timeMatch) return date;
  return `${date} ${timeMatch[1]}:${timeMatch[2]}`;
}

export function todayIso(): string {
  const now = new Date();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${mm}-${dd}`;
}
