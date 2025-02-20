import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { format } from "date-fns";
import { useState } from "react";
import { Link } from "react-router";
import { BRANCH_EVENTS, STANDARD_EVENTS } from "../utils/constants";
import { EventType } from "./event";
import { BranchEvent } from "./global-branch-event";
import { NodeEvent } from "./global-node-event";
import { StandardEvent } from "./global-standard-event";

export const Event = ({ __typename, ...props }: EventType) => {
  const [show, setShow] = useState(false);

  return (
    <Link
      to={`/activities/${props.id}`}
      className={classNames(
        "flex w-full items-center flex-grow gap-3 p-2 rounded-md shadow-sm border transition-all",
        "bg-gray-50 hover:bg-gray-100",
        props.has_children && "bg-custom-blue-500/10 hover:bg-custom-blue-500/20 "
      )}
      onClick={() => {
        setShow(!show);
      }}
    >
      <div className="flex flex-col gap-2 grow">
        {"attributes" in props && <NodeEvent {...props} />}

        {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

        {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}
      </div>

      <div className="text-xs font-medium text-gray-500 flex items-center gap-1">
        <Icon icon={"mdi:source-branch"} />
        {props.branch}
      </div>

      <div className="text-xs font-medium text-gray-500">
        {format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}
      </div>
    </Link>
  );
};
