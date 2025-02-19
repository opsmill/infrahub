import { DateDisplay } from "@/shared/components/display/date-display";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";
import { Transition } from "@headlessui/react";
import { useState } from "react";
import { BRANCH_EVENTS, STANDARD_EVENTS } from "../utils/constants";
import { EventDetails, EventType } from "./event";
import { BranchEvent } from "./global-branch-event";
import { NodeEvent } from "./global-node-event";
import { StandardEvent } from "./global-standard-event";
import { NodeEvents } from "./node-events";

export const Event = ({ __typename, ...props }: EventType) => {
  const [show, setShow] = useState(false);

  return (
    <div className="flex flex-col relative">
      <div
        className={classNames(
          "flex w-full items-center flex-grow gap-3 p-2 rounded-md shadow-sm border",
          props.has_children &&
            "bg-custom-blue-500/10 cursor-pointer hover:bg-custom-blue-500/20 transition-all"
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

      {props.has_children && (
        <Transition
          show={show}
          as={"div"}
          enter="linear duration-100"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="linear duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <NodeEvents parentId={props.id} />
        </Transition>
      )}
    </div>
  );
};
