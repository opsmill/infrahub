import { Icon } from "@iconify-icon/react";
import { useLocation } from "react-router";

import { DateDisplay } from "@/shared/components/display/date-display";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";

import type { EventType } from "@/entities/events/types";
import { EventDetailsPopover } from "@/entities/events/ui/event-details-popover";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";

import { ArtifactEventTitle } from "./artifact-events/artifact-event-title";
import { BranchEventTitle } from "./branch-events/branch-event-title";
import { GroupEventTitle } from "./group-events/group-event-title";
import { EventAttributes } from "./node-events/event-attributes";
import { NodeEventTitle } from "./node-events/node-event-title";
import { ProposedChangeEventTitle } from "./proposed-change-events/proposed-change-event-title";
import { StandardEventTitle } from "./standard-events/standard-event-title";

const EventContent = (props: EventType) => {
  const { pathname } = useLocation();

  if ("attributes" in props) {
    if (pathname === "/") {
      return <NodeEventTitle {...props} />;
    }

    return (
      <>
        <NodeEventTitle {...props} />
        <EventAttributes attributes={props.attributes} />
      </>
    );
  }

  if (
    props.__typename === "BranchCreatedEvent" ||
    props.__typename === "BranchDeletedEvent" ||
    props.__typename === "BranchMergedEvent" ||
    props.__typename === "BranchRebasedEvent"
  ) {
    return <BranchEventTitle {...props} />;
  }

  if (PROPOSED_CHANGE_EVENTS.includes(props.event)) {
    return <ProposedChangeEventTitle {...props} />;
  }

  if (props.__typename === "StandardEvent" && !props.event.includes(".proposed_change.")) {
    return <StandardEventTitle {...props} />;
  }

  if (props.__typename === "GroupEvent") {
    return <GroupEventTitle {...props} />;
  }

  if (props.__typename === "ArtifactEvent") {
    return <ArtifactEventTitle {...props} />;
  }

  return <span className="text-gray-600 text-sm">{props.event}</span>;
};

export const EventCard = (props: EventType) => {
  const { pathname } = useLocation();

  return (
    <div className="flex gap-2">
      <TimelineBorder />

      <div className="flex min-w-0 grow flex-col gap-3 rounded-md border border-gray-200 bg-white p-2 text-sm shadow-xs">
        <EventContent {...props} />

        <div className="flex justify-between text-gray-500">
          <DateDisplay date={props.occurred_at} />

          <div className="flex items-center gap-4">
            {!PROPOSED_CHANGE_EVENTS.includes(props.event) && props.branch && (
              <div className="flex items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap font-medium text-gray-500 text-xs">
                <Icon icon={"mdi:source-branch"} />

                {props.branch}
              </div>
            )}

            {pathname !== "/" && <EventDetailsPopover {...props} />}
          </div>
        </div>
      </div>
    </div>
  );
};
