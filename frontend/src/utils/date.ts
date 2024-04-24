import { format, formatDistance } from "date-fns";

export const formatFullDate = (date: number | Date) => {
  return format(date, "dd/MM/yyyy HH:mm");
};

export const formatRelativeTimeFromNow = (date: number | Date) => {
  return formatDistance(date, new Date(), { addSuffix: true });
};
