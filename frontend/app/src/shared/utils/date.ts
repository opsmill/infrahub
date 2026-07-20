import { TZDate } from "@date-fns/tz";
import { format, formatDistance, getYear } from "date-fns";

export const DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss";

export type DateInput = string | number | Date;

export interface FormatDateOptions {
  pattern: string;
  /** IANA timezone to render in; null/undefined uses the browser's local zone. */
  timezone?: string | null;
}

// Returns `timezone` only if this runtime recognizes it, else undefined (→ browser local zone).
// A zone valid on the preference setter's machine may be absent on the viewer's browser;
// `@date-fns/tz` builds a `TZDate` for an unknown zone without complaint and only throws lazily
// on use, so we validate up front with `Intl`, which rejects an unknown zone synchronously.
function supportedTimezone(timezone?: string | null): string | undefined {
  if (!timezone) {
    return;
  }
  try {
    Intl.DateTimeFormat(undefined, { timeZone: timezone });
    return timezone;
  } catch {
    return;
  }
}

/**
 * Pure date-fns formatter; `TZDate` shifts the wall clock to `timezone` when given.
 * Never throws: an unknown zone falls back to the browser's local zone, and an invalid date
 * or pattern degrades to a readable fallback rather than crashing the render subtree (leaf
 * date renderers have no error boundary).
 */
export function formatWithPattern(
  date: DateInput,
  { pattern, timezone }: FormatDateOptions
): string {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) {
    return String(date);
  }
  const zone = supportedTimezone(timezone);
  try {
    return format(zone ? new TZDate(parsed, zone) : parsed, pattern);
  } catch {
    return parsed.toISOString();
  }
}

export function formatRelativeTimeFromNow(date: DateInput) {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) {
    return String(date);
  }
  return formatDistance(parsed, new Date(), { addSuffix: true });
}

export function isInPreviousYear(date: DateInput) {
  const currentYear = getYear(new Date());
  const previousYear = currentYear - 1;
  return getYear(date) === previousYear;
}
