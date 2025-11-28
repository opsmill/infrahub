import { Icon } from "@iconify-icon/react";
import { useLocation } from "react-router";

import { DateDisplay } from "@/shared/components/display/date-display";
import { TimelineBorder } from "@/shared/components/ui/timeline-border";

import type { EventType } from "@/entities/events/types";
import { ArtifactEventTitle } from "@/entities/events/ui/artifact-events/artifact-event-title";
import { BranchEventTitle } from "@/entities/events/ui/branch-events/branch-event-title";
import { EventDetailsPopover } from "@/entities/events/ui/event-details-popover";
import { GroupEventTitle } from "@/entities/events/ui/group-events/group-event-title";
import { EventAttributes } from "@/entities/events/ui/node-events/event-attributes";
import { NodeEventTitle } from "@/entities/events/ui/node-events/node-event-title";
import { ProposedChangeEventTitle } from "@/entities/events/ui/proposed-change-events/proposed-change-event-title";
import { StandardEventTitle } from "@/entities/events/ui/standard-events/standard-event-title";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";

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
              <div className="flex max-w-[200px] items-center gap-1 font-medium text-gray-500 text-xs">
                <Icon icon={"mdi:source-branch"} className="shrink-0" />

                <span className="truncate">{props.branch}</span>
              </div>
            )}

            {pathname !== "/" && <EventDetailsPopover {...props} />}
          </div>
        </div>
      </div>
    </div>
  );
};
