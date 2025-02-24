import { Link } from "@/shared/components/ui/link";
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
        "grid grid-cols-2 p-2 rounded-md shadow-sm border transition-all",
        "bg-gray-50",
        props.has_children && "bg-custom-blue-500/10"
      )}
    >
      <div className="flex flex-col gap-2 grow">
        {"attributes" in props && <NodeEvent {...props} />}

        {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

        {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}
      </div>

      <div className="grid grid-cols-3 items-center text-right">
        <div className="text-xs font-medium text-gray-500 flex items-center gap-1">
          <Icon icon={"mdi:source-branch"} />
          {props.branch}
        </div>

        <div className="flex text-xs font-medium text-gray-500">
          <span className="mr-2">
            {props.occurred_at && format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}
          </span>
        </div>

        <Link to={`/activities/${props.id}`} className="text-xs text-gray-500">
          View more
        </Link>
      </div>
    </div>
  );
};
