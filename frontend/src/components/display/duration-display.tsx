import { Icon } from "@iconify-icon/react";
import { format, formatDistanceStrict } from "date-fns";
import { Tooltip } from "../utils/tooltip";

type DateDisplayProps = {
  date: number | string | Date;
  endDate?: number | string | Date;
  hideDefault?: boolean;
};

export const getDateDisplay = (date?: number | string | Date) =>
  format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm:ss (O)");

export const DurationDisplay = (props: DateDisplayProps) => {
  const { date, endDate } = props;

  const tooltip = (
    <div className="flex items-center">
      {getDateDisplay(date)}

      <Icon icon="mdi:chevron-right" className="mx-2" />

      {getDateDisplay(endDate)}
    </div>
  );

  return (
    <span className="flex items-center flex-wrap">
      <Tooltip message={tooltip}>
        <span className="text-xs font-normal">
          {formatDistanceStrict(
            date ? new Date(date) : new Date(),
            endDate ? new Date(endDate) : new Date()
          )}
        </span>
      </Tooltip>
    </span>
  );
};
