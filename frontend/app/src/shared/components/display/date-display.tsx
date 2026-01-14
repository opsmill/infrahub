import { differenceInDays, format, formatDistanceToNow } from "date-fns";

import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { isInPreviousYear } from "@/shared/utils/date";

type DateDisplayProps = {
  date?: number | string | Date | null;
  hideDefault?: boolean;
  className?: string;
  containerClassName?: string;
  dateFormat?: string;
};

export const getDateDisplay = (date?: number | string | Date | null) =>
  format(date ? new Date(date) : new Date(), "yyyy-MM-dd HH:mm:ss (O)");

export const DateDisplay = ({
  date,
  hideDefault,
  className,
  containerClassName,
  dateFormat,
}: DateDisplayProps) => {
  if (!date && hideDefault) {
    return null;
  }

  const dateData = date ? new Date(date) : new Date();

  const distanceFromNow = differenceInDays(new Date(), dateData);

  if (distanceFromNow > 7 || dateFormat) {
    const newDateFormat = dateFormat ?? (isInPreviousYear(dateData) ? "d MMM yyyy" : "d MMM");

    return (
      <span className={classNames("flex flex-wrap items-center", containerClassName)}>
        <Tooltip enabled content={getDateDisplay(dateData)}>
          <span className={classNames("truncate font-normal text-xs", className)}>
            {format(dateData, newDateFormat)}
          </span>
        </Tooltip>
      </span>
    );
  }

  return (
    <span className={classNames("flex flex-wrap items-center", containerClassName)}>
      <Tooltip enabled content={getDateDisplay(date)}>
        <span className={classNames("truncate font-normal text-xs", className)}>
          {formatDistanceToNow(dateData, { addSuffix: true })}
        </span>
      </Tooltip>
    </span>
  );
};
