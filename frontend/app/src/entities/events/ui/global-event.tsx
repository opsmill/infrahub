import { BranchEvent, EventType } from "@/entities/events/types";
import { ArtifactEvent, GroupEvent, StandardEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";

import { ArtifactEventTitle } from "./artifact-events/artifact-event-title";
import { BranchEventTitle } from "./branch-events/branch-event-title";
import { GroupEventTitle } from "./group-events/group-event-title";
import { NodeEventTitle } from "./node-events/node-event-title";
import { StandardEventTitle } from "./standard-events/standard-event-title";

const GlobalEventDisplay = ({ __typename, ...props }: EventType) => {
  if ("attributes" in props) {
    return <NodeEventTitle {...props} />;
  }

  if (
    __typename === "BranchCreatedEvent" ||
    __typename === "BranchDeletedEvent" ||
    __typename === "BranchMergedEvent" ||
    __typename === "BranchRebasedEvent"
  ) {
    return <BranchEventTitle {...(props as BranchEvent)} />;
  }

  if (__typename === "StandardEvent") {
    return <StandardEventTitle {...(props as StandardEvent)} />;
  }

  if (__typename === "GroupEvent") {
    return <GroupEventTitle {...(props as GroupEvent)} />;
  }

  if (__typename === "ArtifactEvent") {
    return <ArtifactEventTitle {...(props as ArtifactEvent)} />;
  }

  return <span className="flex items-center text-sm text-gray-500 ">{props.event}</span>;
};

export const Event = (props: EventType) => {
  return (
    <div
      className={classNames(
        "grid grid-cols-8 relative gap-2 p-2",
        "rounded-md shadow-xs transition-all border border-gray-200 bg-gray-50"
      )}
    >
      <div className="flex items-center text-xs font-medium text-gray-500 whitespace-nowrap">
        <Tooltip enabled content={format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}>
          <span>{format(new Date(props.occurred_at), "MMM dd, HH:mm:ss")}</span>
        </Tooltip>
      </div>

      <div className="col-span-5 flex item-center gap-4 overflow-hidden">
        <GlobalEventDisplay {...props} />
      </div>

      <div className="text-xs font-medium text-gray-500 flex items-center gap-1 whitespace-nowrap overflow-hidden text-ellipsis">
        {props.branch && (
          <>
            <Icon icon={"mdi:source-branch"} />

            {props.branch}
          </>
        )}
      </div>

      <div className="relative">
        <Link to={`/activities/${props.id}`} className="text-xs text-gray-500">
          View details
        </Link>

        {props.has_children && (
          <Tooltip enabled content="Contains sub activities">
            <Icon
              icon={"mdi:subtasks"}
              className="absolute right-2 rounded-full text-custom-blue-500 bg-custom-blue-500/10 p-1.5"
              data-testid="activity-has-children-icon"
            />
          </Tooltip>
        )}
      </div>
    </div>
  );
};
