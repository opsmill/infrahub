import { Tooltip } from "@infrahub/ui";

import { DateDisplay } from "@/shared/components/display/date-display";
import { Icon } from "@/shared/components/display/icon";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import type { EventType } from "@/entities/events/domain/model/event";
import { EventTitle } from "@/entities/events/ui/event-title";

export const Event = (props: EventType) => {
  return (
    <div
      className={classNames(
        "relative grid grid-cols-8 gap-2 p-2",
        "rounded-md border bg-card shadow-card transition-all"
      )}
    >
      <div className="flex items-center whitespace-nowrap font-medium text-foreground-muted text-xs">
        <DateDisplay date={props.occurred_at} fullTimestamp />
      </div>

      <div className="item-center col-span-5 flex gap-4 overflow-hidden">
        <EventTitle event={props} />
      </div>

      <div className="flex items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap font-medium text-foreground-muted text-xs">
        {props.branch && (
          <>
            <Icon icon={"mdi:source-branch"} />

            {props.branch}
          </>
        )}
      </div>

      <div className="relative">
        <Link to={`/activities/${props.id}`} className="text-foreground-muted text-xs">
          View details
        </Link>

        {props.has_children && (
          <Tooltip message="Contains sub activities" nonInteractiveTrigger>
            <Icon
              icon={"mdi:subtasks"}
              className="absolute right-2 rounded-full bg-accent/10 p-1.5 text-accent"
              data-testid="activity-has-children-icon"
            />
          </Tooltip>
        )}
      </div>
    </div>
  );
};
