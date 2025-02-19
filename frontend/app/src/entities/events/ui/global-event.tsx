import { DateDisplay } from "@/shared/components/display/date-display";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { BRANCH_EVENTS, STANDARD_EVENTS } from "../utils/constants";
import { EventDetails, EventType } from "./event";
import { BranchEvent } from "./global-branch-event";
import { NodeEvent } from "./global-node-event";
import { StandardEvent } from "./global-standard-event";

export const Event = ({ __typename, ...props }: EventType) => {
  return (
    <div className="flex gap-2">
      <div className="flex items-center flex-grow gap-3 p-2 rounded-md shadow-sm border">
        <div className="flex flex-col gap-2 grow">
          {"attributes" in props && <NodeEvent {...props} />}

          {BRANCH_EVENTS.includes(__typename) && <BranchEvent {...props} />}

          {STANDARD_EVENTS.includes(__typename) && <StandardEvent {...props} />}
        </div>

        <Popover>
          <PopoverTrigger>
            <p className="text-sm underline text-gray-600 dark:text-neutral-400">View more.</p>
          </PopoverTrigger>

          <PopoverContent className="w-full">
            <EventDetails {...props} />
          </PopoverContent>
        </Popover>

        <div className="text-xs font-medium text-gray-500 dark:text-neutral-400">
          <DateDisplay date={props.occurred_at} />
        </div>
      </div>
    </div>
  );
};
