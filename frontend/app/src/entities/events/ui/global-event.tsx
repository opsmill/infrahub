import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";

import type {
  ArtifactEvent,
  GroupEvent,
  StandardEvent,
} from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import type { BranchEvent, EventType } from "@/entities/events/types";
import { ArtifactEventTitle } from "@/entities/events/ui/artifact-events/artifact-event-title";
import { BranchEventTitle } from "@/entities/events/ui/branch-events/branch-event-title";
import { GroupEventTitle } from "@/entities/events/ui/group-events/group-event-title";
import { NodeEventTitle } from "@/entities/events/ui/node-events/node-event-title";
import { ProposedChangeEventTitle } from "@/entities/events/ui/proposed-change-events/proposed-change-event-title";
import { StandardEventTitle } from "@/entities/events/ui/standard-events/standard-event-title";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";

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

  if (__typename === "StandardEvent" && PROPOSED_CHANGE_EVENTS.includes(props.event)) {
    return <ProposedChangeEventTitle {...props} />;
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

  return <span className="flex items-center text-gray-500 text-sm dark:text-gray-400">{props.event}</span>;
};

export const Event = (props: EventType) => {
  return (
    <div
      className={classNames(
        "relative grid grid-cols-8 gap-2 p-2",
        "rounded-md border border-gray-200 bg-gray-50 shadow-xs transition-all",
        "dark:border-slate-600 dark:bg-slate-700"
      )}
    >
      <div className="flex items-center whitespace-nowrap font-medium text-gray-500 text-xs dark:text-gray-400">
        <Tooltip enabled content={format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}>
          <span>{format(new Date(props.occurred_at), "MMM dd, HH:mm:ss")}</span>
        </Tooltip>
      </div>

      <div className="item-center col-span-5 flex gap-4 overflow-hidden">
        <GlobalEventDisplay {...props} />
      </div>

      <div className="flex items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap font-medium text-gray-500 text-xs dark:text-gray-400">
        {props.branch && (
          <>
            <Icon icon={"mdi:source-branch"} />

            {props.branch}
          </>
        )}
      </div>

      <div className="relative">
        <Link to={`/activities/${props.id}`} className="text-gray-500 text-xs dark:text-gray-400">
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
