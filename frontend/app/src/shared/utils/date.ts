import { TZDate } from "@date-fns/tz";
import { format, formatDistance, getYear } from "date-fns";

export const DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss";

export type DateInput = string | number | Date;

export interface FormatDateOptions {
  pattern: string;
  /** IANA timezone to render in; null/undefined uses the browser's local zone. */
  timezone?: string | null;
}

/** Pure date-fns formatter; `TZDate` shifts the wall clock to `timezone` when given. */
export function formatDate(date: DateInput, { pattern, timezone }: FormatDateOptions): string {
  if (timezone) {
    return format(new TZDate(new Date(date), timezone), pattern);
  }
  return format(new Date(date), pattern);
}

export function formatRelativeTimeFromNow(date: DateInput) {
  return formatDistance(date, new Date(), { addSuffix: true });
}

export function isInPreviousYear(date: DateInput) {
  const currentYear = getYear(new Date());
  const previousYear = currentYear - 1;
  return getYear(date) === previousYear;
}
