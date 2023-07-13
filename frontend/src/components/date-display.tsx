import { format, formatDistanceToNow } from "date-fns";
import { Pill } from "./pill";

type DateDisplayProps = {
  date?: number | string | Date;
  hideDefault?: boolean;
};

export const getDateDisplay = (date?: number | string | Date) =>
  format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm (O)");

export const DateDisplay = (props: DateDisplayProps) => {
  const { date, hideDefault } = props;

  if (!date && hideDefault) {
    return null;
  }

  return (
    <span className="">
      <Pill className="text-sm font-normal">{getDateDisplay(date)}</Pill>

      <i className="text-xs">
        ({formatDistanceToNow(date ? new Date(date) : new Date(), { addSuffix: true })})
      </i>
    </span>
  );
};
