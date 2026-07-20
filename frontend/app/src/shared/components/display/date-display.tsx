import { Tooltip } from "@infrahub/ui";
import { differenceInDays } from "date-fns";
import type React from "react";

import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";
import { formatWithPattern } from "@/shared/utils/date";

type DateDisplayProps = {
  date?: number | string | Date | null;
  hideDefault?: boolean;
  className?: string;
  containerClassName?: string;
  /** Explicit date-fns pattern escape hatch: overrides the pattern but still renders in the preferred timezone. */
  dateFormat?: string;
  /** Forces the full preferred datetime inline; omitted keeps the compact "x ago" / date heuristic. */
  fullTimestamp?: boolean;
};

export const DateDisplay = ({
  date,
  hideDefault,
  className,
  containerClassName,
  dateFormat,
  fullTimestamp,
}: DateDisplayProps) => {
  const { formatDate, timezone } = useFormatDate();

  if (!date && hideDefault) {
    return null;
  }

  const dateData = date ? new Date(date) : new Date();
  const tooltipMessage = formatDate(dateData, "datetime");

  const wrap = (content: React.ReactNode) => (
    <span className={classNames("flex flex-wrap items-center", containerClassName)}>
      <Tooltip message={tooltipMessage} nonInteractiveTrigger>
        <span className={classNames("truncate font-normal text-xs", className)}>{content}</span>
      </Tooltip>
    </span>
  );

  if (fullTimestamp) {
    return wrap(tooltipMessage);
  }

  if (dateFormat) {
    return wrap(formatWithPattern(dateData, { pattern: dateFormat, timezone }));
  }

  // > 7 days old → preferred date; recent → "x ago".
  if (differenceInDays(new Date(), dateData) > 7) {
    return wrap(formatDate(dateData, "date"));
  }

  return wrap(formatDate(dateData, "relative"));
};
