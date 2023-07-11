import { format, formatDistanceToNow } from "date-fns";
import { Tooltip } from "./tooltip";

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
    <span className="font-normal">
      <Tooltip
        message={formatDistanceToNow(date ? new Date(date) : new Date(), {
          addSuffix: true,
        })}>
        {format(date ? new Date(date) : new Date(), "MM/dd/yyy HH:mm")}
      </Tooltip>
    </span>
  );
};
