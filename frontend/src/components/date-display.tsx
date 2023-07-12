import { format, formatDistanceToNow } from "date-fns";
import { Pill } from "./pill";

type DateDisplayProps = {
  date?: number | string | Date;
  hideDefault?: boolean;
};

export const DateDisplay = (props: DateDisplayProps) => {
  const { date, hideDefault } = props;

  if (!date && hideDefault) {
    return null;
  }

  return (
    <span className="">
      <Pill className="text-sm">
        {format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm (O)")}
      </Pill>

      <i className="text-xs">
        ({formatDistanceToNow(date ? new Date(date) : new Date(), { addSuffix: true })})
      </i>
    </span>
  );
};
