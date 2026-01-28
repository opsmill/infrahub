import { format, formatDistance, getYear } from "date-fns";

export const DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss";
export const DATE_TIME_FORMAT_WITH_TZ = "yyyy-MM-dd HH:mm:ss (O)";

export function formatFullDate(date: string | number | Date) {
  return format(date, DATE_TIME_FORMAT);
}

export function formatFullDateWithTz(date: string | number | Date) {
  return format(date, DATE_TIME_FORMAT_WITH_TZ);
}

export function formatRelativeTimeFromNow(date: number | Date) {
  return formatDistance(date, new Date(), { addSuffix: true });
}

export function isInPreviousYear(date: string | number | Date) {
  const currentYear = getYear(new Date());
  const previousYear = currentYear - 1;
  return getYear(date) === previousYear;
}
