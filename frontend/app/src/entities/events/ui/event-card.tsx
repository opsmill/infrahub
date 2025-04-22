import { DateDisplay } from "@/shared/components/display/date-display";

import { EventType } from "@/entities/events/types";
import { EventDetailsPopover } from "@/entities/events/ui/event-details-popover";

import { TimelineBorder } from "@/shared/components/ui/timeline-border";
import { Icon } from "@iconify-icon/react";
import { ArtifactEventTitle } from "./artifact-events/artifact-event-title";
import { BranchEventTitle } from "./branch-events/branch-event-title";
import { GroupEventTitle } from "./group-events/group-event-title";
import { EventAttributes } from "./node-events/event-attributes";
import { NodeEventTitle } from "./node-events/node-event-title";
import { StandardEventTitle } from "./standard-events/standard-event-title";

export const EventCard = (props: EventType) => {
  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex grow gap-3 p-2 rounded-md shadow-xs border border-gray-200 bg-white">
        <div className="flex flex-col gap-2 grow">
          {"attributes" in props && <NodeEventTitle {...props} />}

          {"attributes" in props && <EventAttributes attributes={props.attributes} />}

          {(props.__typename === "BranchCreatedEvent" ||
            props.__typename === "BranchDeletedEvent" ||
            props.__typename === "BranchMergedEvent" ||
            props.__typename === "BranchRebasedEvent") && <BranchEventTitle {...props} />}

          {props.__typename === "StandardEvent" && <StandardEventTitle {...props} />}

          {props.__typename === "GroupEvent" && <GroupEventTitle {...props} />}

          {props.__typename === "ArtifactEvent" && <ArtifactEventTitle {...props} />}

          <div className="flex justify-between text-gray-500">
            <DateDisplay date={props.occurred_at} />

            <div className="flex items-center gap-4">
              {props.branch && (
                <div className="text-xs font-medium text-gray-500 flex items-center gap-1 whitespace-nowrap overflow-hidden text-ellipsis">
                  <Icon icon={"mdi:source-branch"} />

                  {props.branch}
                </div>
              )}

              <EventDetailsPopover {...props} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
