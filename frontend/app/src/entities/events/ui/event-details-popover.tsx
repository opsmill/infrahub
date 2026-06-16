import { Popover, PopoverTrigger, ScrollArea } from "@infrahub/ui";
import { InfoIcon } from "lucide-react";
import { Button } from "react-aria-components";

import type { EventType } from "@/entities/events/types";

import { EventDetails } from "./event-details";

export function EventDetailsPopover(props: EventType) {
  return (
    <PopoverTrigger>
      <Button className="flex items-center gap-1 rounded-md px-1 py-0.5 text-gray-600 text-xs transition-all hover:bg-gray-100 hover:text-gray-700">
        View more <InfoIcon className="size-3" />
      </Button>

      <Popover className="max-h-64 overflow-auto">
        <ScrollArea scrollY>
          <EventDetails {...props} />
        </ScrollArea>
      </Popover>
    </PopoverTrigger>
  );
}
