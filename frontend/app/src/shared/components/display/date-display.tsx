import { differenceInDays, format, formatDistanceToNow } from "date-fns";

import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { isInPreviousYear } from "@/shared/utils/date";

type DateDisplayProps = {
  date?: number | string | Date;
  hideDefault?: boolean;
  className?: string;
  containerClassName?: string;
};

export const getDateDisplay = (date?: number | string | Date) =>
  format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm:ss (O)");

export const DateDisplay = (props: DateDisplayProps) => {
  const { date, hideDefault, className, containerClassName } = props;

  if (!date && hideDefault) {
    return null;
  }

  const dateData = date ? new Date(date) : new Date();

  const distanceFromNow = differenceInDays(new Date(), dateData);

  if (distanceFromNow > 7) {
    const dateFormat = isInPreviousYear(dateData) ? "d MMM yyyy" : "d MMM";

    return (
      <span className={classNames("flex items-center flex-wrap", containerClassName)}>
        <Tooltip enabled content={getDateDisplay(dateData)}>
          <span className={classNames("text-xs font-normal", className)}>
            {format(dateData, dateFormat)}
          </span>
        </Tooltip>
      </span>
    );
  }

  return (
    <span className={classNames("flex items-center flex-wrap", containerClassName)}>
      <Tooltip enabled content={getDateDisplay(date)}>
        <span className={classNames("text-xs font-normal", className)}>
          {formatDistanceToNow(dateData, { addSuffix: true })}
        </span>
      </Tooltip>
    </span>
  );
};
