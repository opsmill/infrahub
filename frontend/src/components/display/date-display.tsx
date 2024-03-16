import { differenceInDays, format, formatDistanceToNow } from "date-fns";
import { Tooltip } from "../utils/tooltip";

type DateDisplayProps = {
  date?: number | string | Date;
  hideDefault?: boolean;
};

export const getDateDisplay = (date?: number | string | Date) =>
  format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm:ss (O)");

export const DateDisplay = (props: DateDisplayProps) => {
  const { date, hideDefault } = props;

  if (!date && hideDefault) {
    return null;
  }

  const dateData = date ? new Date(date) : new Date();

  const distanceFromNow = differenceInDays(new Date(), dateData);

  if (distanceFromNow > 7) {
    return (
      <span className="flex items-center flex-wrap">
        <Tooltip message={getDateDisplay(date)}>
          <span className="text-xs font-normal">{format(dateData, "MMM d")}</span>
        </Tooltip>
      </span>
    );
  }

  return (
    <span className="flex items-center flex-wrap">
      <Tooltip message={getDateDisplay(date)}>
        <span className="text-xs font-normal">
          {formatDistanceToNow(dateData, { addSuffix: true })}
        </span>
      </Tooltip>
    </span>
  );
};
