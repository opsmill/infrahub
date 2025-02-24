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
        "grid grid-cols-3 relative gap-8 rounded-md shadow-sm transition-all",
        "bg-gray-50"
      )}
    >
      <div className="col-span-2 p-2.5">
        {"attributes" in props && <NodeEvent {...props} />}

        {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

        {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}
      </div>

      <div className="grid grid-cols-3 col-span-1 items-center text-right border-r border-b rounded-r-md border-custom-blue-500 p-2.5 relative">
        <div className="text-xs font-medium text-gray-500 flex items-center gap-1">
          {props.has_children && (
            <Tooltip enabled content="Contains sub activities">
              <Icon
                icon={"mdi:subtasks"}
                className="absolute -left-8 rounded-full text-white bg-custom-blue-500 p-1.5"
              />
            </Tooltip>
          )}

          <Icon icon={"mdi:source-branch"} />
          {props.branch}
        </div>

        <div className="flex text-xs font-medium text-gray-500 whitespace-nowrap">
          {props.occurred_at && format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}
        </div>

        <Link to={`/activities/${props.id}`} className="text-xs text-gray-500">
          View more
        </Link>
      </div>
    </div>
  );
};
