import { Card } from "@infrahub/ui";
import { useLocation } from "react-router";

import { DateDisplay } from "@/shared/components/display/date-display";
import { Icon } from "@/shared/components/display/icon";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";

import type { EventType } from "@/entities/events/domain/model/event";
import { EventDetailsPopover } from "@/entities/events/ui/event-details-popover";
import { EventTitle } from "@/entities/events/ui/event-title";
import { EventAttributes } from "@/entities/events/ui/node-events/event-attributes";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/domain/model/proposed-change-events";

export const EventCard = (props: EventType) => {
  const { pathname } = useLocation();

  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <Card className="min-w-0 grow gap-3 rounded-md p-2 text-sm">
        <EventTitle event={props} />

        {"attributes" in props && pathname !== "/" && (
          <EventAttributes attributes={props.attributes} />
        )}

        <div className="flex justify-between text-foreground-muted">
          <DateDisplay date={props.occurred_at} />

          <div className="flex items-center gap-4">
            {!PROPOSED_CHANGE_EVENTS.includes(props.event) && props.branch && (
              <div className="flex max-w-50 items-center gap-1 font-medium text-foreground-muted text-xs">
                <Icon icon={"mdi:source-branch"} className="shrink-0" />

                <span className="truncate">{props.branch}</span>
              </div>
            )}

            {pathname !== "/" && <EventDetailsPopover {...props} />}
          </div>
        </div>
      </Card>
    </div>
  );
};
