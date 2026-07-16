import { Tooltip } from "@infrahub/ui";
import { differenceInDays, format, formatDistanceToNow } from "date-fns";
import type React from "react";

import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";

type DateDisplayProps = {
  date?: number | string | Date | null;
  hideDefault?: boolean;
  className?: string;
  containerClassName?: string;
  /** Explicit date-fns pattern escape hatch: rendered inline verbatim, bypassing preferences. */
  dateFormat?: string;
  /** `"datetime"` forces the full preferred datetime inline; omitted keeps the compact heuristic. */
  variant?: "datetime";
};

export const DateDisplay = ({
  date,
  hideDefault,
  className,
  containerClassName,
  dateFormat,
  variant,
}: DateDisplayProps) => {
  const { formatDate } = useFormatDate();

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

  if (variant === "datetime") {
    return wrap(formatDate(dateData, "datetime"));
  }

  if (dateFormat) {
    return wrap(format(dateData, dateFormat));
  }

  // > 7 days old → preferred date; recent → "x ago".
  if (differenceInDays(new Date(), dateData) > 7) {
    return wrap(formatDate(dateData, "date"));
  }

  return wrap(formatDistanceToNow(dateData, { addSuffix: true }));
};
