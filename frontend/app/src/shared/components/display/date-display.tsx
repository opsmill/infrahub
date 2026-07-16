import { Tooltip } from "@infrahub/ui";
import { differenceInDays, format, formatDistanceToNow } from "date-fns";
import type React from "react";

import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";
import { formatFullDateWithTz } from "@/shared/utils/date";

type DateDisplayProps = {
  date?: number | string | Date | null;
  hideDefault?: boolean;
  className?: string;
  containerClassName?: string;
  /** Explicit date-fns pattern escape hatch: renders exactly this pattern inline (no heuristic). */
  dateFormat?: string;
  /**
   * `"datetime"` renders the user's full preferred datetime + timezone inline. Omitted (default)
   * keeps the historic relative/compact heuristic below.
   */
  variant?: "datetime";
};

/**
 * Standalone full-datetime string with timezone. Kept as a NON-preference-aware helper for the
 * (non-React) callers that import it directly; preference-aware rendering flows through
 * {@link DateDisplay} / `useFormatDate` instead.
 */
export const getDateDisplay = (date?: number | string | Date | null) =>
  formatFullDateWithTz(date ? new Date(date) : new Date());

export const DateDisplay = ({
  date,
  hideDefault,
  className,
  containerClassName,
  dateFormat,
  variant,
}: DateDisplayProps) => {
  // Reads the shared date-preferences context; falls back to browser-locale formatting when no
  // provider is mounted, so DateDisplay never crashes outside the provider.
  const { formatDate } = useFormatDate();

  if (!date && hideDefault) {
    return null;
  }

  const dateData = date ? new Date(date) : new Date();

  // The tooltip always shows the user's full preferred datetime + timezone.
  const tooltipMessage = formatDate(dateData, "datetime");

  const wrap = (content: React.ReactNode) => (
    <span className={classNames("flex flex-wrap items-center", containerClassName)}>
      <Tooltip message={tooltipMessage} nonInteractiveTrigger>
        <span className={classNames("truncate font-normal text-xs", className)}>{content}</span>
      </Tooltip>
    </span>
  );

  // Explicit full-timestamp variant: render the user's preferred datetime inline.
  if (variant === "datetime") {
    return wrap(formatDate(dateData, "datetime"));
  }

  // Explicit pattern escape hatch: render exactly this pattern inline (no heuristic, no preference).
  if (dateFormat) {
    return wrap(format(dateData, dateFormat));
  }

  const distanceFromNow = differenceInDays(new Date(), dateData);

  // Compact branch: > 7 days old → the user's preferred date, honouring their format + timezone.
  if (distanceFromNow > 7) {
    return wrap(formatDate(dateData, "date"));
  }

  // Relative branch: recent dates with no override.
  return wrap(formatDistanceToNow(dateData, { addSuffix: true }));
};
