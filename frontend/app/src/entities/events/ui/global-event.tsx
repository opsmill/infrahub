import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";
import { BRANCH_EVENTS, STANDARD_EVENTS } from "../utils/constants";
import { EventType } from "./event";
import { BranchEvent } from "./global-branch-event";
import { NodeEvent } from "./global-node-event";
import { StandardEvent } from "./global-standard-event";

export const Event = ({ __typename, ...props }: EventType) => {
  return (
    <div
      className={classNames(
        "grid grid-cols-4 relative gap-8",
        "rounded-md shadow-sm transition-all border bg-gray-50"
      )}
    >
      <div className="col-span-3 flex item-center gap-4 p-2.5">
        <div className="flex items-center text-xs font-medium text-gray-500 whitespace-nowrap">
          <Tooltip enabled content={props.occurred_at}>
            <span>{format(new Date(props.occurred_at), "MMM dd, HH:mm:ss")}</span>
          </Tooltip>
        </div>

        {"attributes" in props && <NodeEvent {...props} />}

        {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

        {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}
      </div>

      <div className="grid grid-cols-2 items-center text-right p-2.5 relative">
        <div className="text-xs font-medium text-gray-500 flex items-center gap-1">
          {props.has_children && (
            <Tooltip enabled content="Contains sub activities">
              <Icon
                icon={"mdi:subtasks"}
                className="absolute -left-8 rounded-full text-custom-blue-500 bg-custom-blue-500/10 p-1.5"
              />
            </Tooltip>
          )}

          <Icon icon={"mdi:source-branch"} />

          {props.branch}
        </div>

        <Link to={`/activities/${props.id}`} className="text-xs text-gray-500">
          View more
        </Link>
      </div>
    </div>
  );
};
