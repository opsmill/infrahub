import { format, formatDistance, getYear } from "date-fns";

export const DATE_TIME_FORMAT = "yyyy-MM-dd HH:mm:ss (O)";

export function formatFullDate(date: string | number | Date) {
  return format(date, "dd/MM/yyyy HH:mm");
}

export function formatRelativeTimeFromNow(date: number | Date) {
  return formatDistance(date, new Date(), { addSuffix: true });
}

export function isInPreviousYear(date: string | number | Date) {
  const currentYear = getYear(new Date());
  const previousYear = currentYear - 1;
  return getYear(date) === previousYear;
}
