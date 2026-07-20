import { Icon } from "@iconify-icon/react";
import { Tooltip } from "@infrahub/ui";
import { formatDistanceStrict } from "date-fns";

import { useFormatDate } from "@/shared/context/date-preferences-context";

type DateDisplayProps = {
  date: number | string | Date;
  endDate?: number | string | Date;
  hideDefault?: boolean;
};

export const DurationDisplay = (props: DateDisplayProps) => {
  const { date, endDate } = props;
  const { formatDate } = useFormatDate();

  const tooltip = (
    <div className="flex items-center">
      {formatDate(date, "datetime")}

      <Icon icon="mdi:chevron-right" className="mx-2" />

      {formatDate(endDate ?? new Date(), "datetime")}
    </div>
  );

  return (
    <span className="flex flex-wrap items-center">
      <Tooltip message={tooltip} nonInteractiveTrigger>
        <span className="font-normal text-xs">
          {formatDistanceStrict(
            date ? new Date(date) : new Date(),
            endDate ? new Date(endDate) : new Date()
          )}
        </span>
      </Tooltip>
    </span>
  );
};
