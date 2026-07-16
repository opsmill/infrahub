import { TZDate } from "@date-fns/tz";
import { format, formatDistance, getYear } from "date-fns";

export const DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss";

export type DateInput = string | number | Date;

export interface FormatDateOptions {
  /** date-fns pattern to render with. */
  pattern: string;
  /**
   * IANA timezone name (e.g. "Europe/Paris") to render `date` in. When null/undefined the
   * date is rendered in the browser's local zone.
   */
  timezone?: string | null;
}

/**
 * Pure, hook-free date formatter — the single low-level primitive every preference-aware
 * renderer builds on. Renders `date` with the given date-fns `pattern`, in `timezone` when
 * provided (via `@date-fns/tz`'s {@link TZDate}, which shifts the wall-clock reading to that
 * IANA zone) or in the browser's local zone otherwise. Because it takes an explicit pattern +
 * timezone, it carries no preference/context dependency and is trivially unit-testable.
 */
export function formatDate(date: DateInput, { pattern, timezone }: FormatDateOptions): string {
  if (timezone) {
    // TZDate reinterprets the instant in `timezone`, so `format` emits that zone's wall clock.
    return format(new TZDate(new Date(date), timezone), pattern);
  }
  return format(new Date(date), pattern);
}

export function formatFullDate(date: DateInput) {
  return format(date, DATE_TIME_FORMAT);
}

export function formatRelativeTimeFromNow(date: DateInput) {
  return formatDistance(date, new Date(), { addSuffix: true });
}

export function isInPreviousYear(date: DateInput) {
  const currentYear = getYear(new Date());
  const previousYear = currentYear - 1;
  return getYear(date) === previousYear;
}
