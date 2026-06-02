import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";

import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames, warnUnexpectedType } from "@/shared/utils/common";

import type { EventType } from "@/entities/events/types";
import { AccountLoggedInEventTitle } from "@/entities/events/ui/account-events/account-logged-in-event-title";
import { AccountLoggedOutEventTitle } from "@/entities/events/ui/account-events/account-logged-out-event-title";
import { ArtifactEventTitle } from "@/entities/events/ui/artifact-events/artifact-event-title";
import { BranchEventTitle } from "@/entities/events/ui/branch-events/branch-event-title";
import { GroupAutoCreateEventTitle } from "@/entities/events/ui/group-auto-create-events/group-auto-create-event-title";
import { GroupEventTitle } from "@/entities/events/ui/group-events/group-event-title";
import { NodeEventTitle } from "@/entities/events/ui/node-events/node-event-title";
import { ProposedChangeEventTitle } from "@/entities/events/ui/proposed-change-events/proposed-change-event-title";
import { StandardEventTitle } from "@/entities/events/ui/standard-events/standard-event-title";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";

const GlobalEventDisplay = (props: EventType) => {
  if ("attributes" in props) {
    return <NodeEventTitle {...props} />;
  }

  switch (props.__typename) {
    case "BranchCreatedEvent":
    case "BranchDeletedEvent":
    case "BranchMergedEvent":
    case "BranchRebasedEvent": {
      return <BranchEventTitle {...props} />;
    }
    case "StandardEvent": {
      if (PROPOSED_CHANGE_EVENTS.includes(props.event)) {
        return <ProposedChangeEventTitle {...props} />;
      }
      return <StandardEventTitle {...props} />;
    }
    case "GroupEvent": {
      return <GroupEventTitle {...props} />;
    }
    case "GroupAutoCreatedEventType":
    case "GroupAutoCreateRejectedEventType":
    case "GroupAutoCreateCappedEventType": {
      return <GroupAutoCreateEventTitle {...props} />;
    }
    case "ArtifactEvent": {
      return <ArtifactEventTitle {...props} />;
    }
    case "AccountLoggedInEventType": {
      return <AccountLoggedInEventTitle {...props} />;
    }
    case "AccountLoggedOutEventType": {
      return <AccountLoggedOutEventTitle {...props} />;
    }
    default: {
      warnUnexpectedType(props);
      return (
        <span className="flex items-center text-gray-500 text-sm">
          {(props as EventType).event}
        </span>
      );
    }
  }
};

export const Event = (props: EventType) => {
  return (
    <div
      className={classNames(
        "relative grid grid-cols-8 gap-2 p-2",
        "rounded-md border border-gray-200 bg-gray-50 shadow-xs transition-all"
      )}
    >
      <div className="flex items-center whitespace-nowrap font-medium text-gray-500 text-xs">
        <Tooltip enabled content={format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}>
          <span>{format(new Date(props.occurred_at), "MMM dd, HH:mm:ss")}</span>
        </Tooltip>
      </div>

      <div className="item-center col-span-5 flex gap-4 overflow-hidden">
        <GlobalEventDisplay {...props} />
      </div>

      <div className="flex items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap font-medium text-gray-500 text-xs">
        {props.branch && (
          <>
            <Icon icon={"mdi:source-branch"} />

            {props.branch}
          </>
        )}
      </div>

      <div className="relative">
        <Link to={`/activities/${props.id}`} className="text-gray-500 text-xs">
          View details
        </Link>

        {props.has_children && (
          <Tooltip enabled content="Contains sub activities">
            <Icon
              icon={"mdi:subtasks"}
              className="absolute right-2 rounded-full bg-custom-blue-500/10 p-1.5 text-custom-blue-500"
              data-testid="activity-has-children-icon"
            />
          </Tooltip>
        )}
      </div>
    </div>
  );
};
