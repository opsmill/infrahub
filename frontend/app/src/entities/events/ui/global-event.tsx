import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";
import { BRANCH_EVENTS, GROUP_EVENTS, STANDARD_EVENTS } from "../utils/constants";
import { EventType } from "./event";
import { BranchEvent } from "./global-branch-event";
import { GroupEvent } from "./global-group-event";
import { NodeEvent } from "./global-node-event";
import { StandardEvent } from "./global-standard-event";

const GlobalEventDisplay = ({ __typename, ...props }: EventType) => {
  if ("attributes" in props) {
    return <NodeEvent {...props} />;
  }

  if (BRANCH_EVENTS.includes(__typename)) {
    return <BranchEvent {...props} />;
  }

  if (STANDARD_EVENTS.includes(__typename)) {
    return <StandardEvent {...props} />;
  }

  if (GROUP_EVENTS.includes(__typename)) {
    return <GroupEvent {...props} />;
  }

  return <span className="flex items-center text-sm text-gray-500 ">{props.event}</span>;
};

export const Event = (props: EventType) => {
  return (
    <div
      className={classNames(
        "grid grid-cols-8 relative gap-2 p-2",
        "rounded-md shadow-sm transition-all border bg-gray-50"
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

      <div className="text-xs font-medium text-gray-500 flex items-center gap-1">
        {props.branch && (
          <>
            <Icon icon={"mdi:source-branch"} />

            {props.branch}
          </>
        )}
      </div>

      <div className="relative">
        <Link to={`/activities/${props.id}`} className="text-xs text-gray-500">
          View more
        </Link>

        {props.has_children && (
          <Tooltip enabled content="Contains sub activities">
            <Icon
              icon={"mdi:subtasks"}
              className="absolute right-2 rounded-full text-custom-blue-500 bg-custom-blue-500/10 p-1.5"
            />
          </Tooltip>
        )}
      </div>
    </div>
  );
};
