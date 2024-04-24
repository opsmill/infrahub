import { format, formatDistance } from "date-fns";

export const formatFullDate = (date: number | Date) => {
  return format(date, "MM/dd/yyyy hh:mma");
};

export const formatRelativeTimeFromNow = (date: number | Date) => {
  return formatDistance(date, new Date(), { addSuffix: true });
};
