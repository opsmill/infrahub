import { EventType } from "@/entities/events/types";

import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { InfoIcon } from "lucide-react";
import { EventDetails } from "./event-details";

export function EventDetailsPopover(props: EventType) {
  return (
    <Popover>
      <PopoverTrigger className="flex items-center px-1 py-0.5 rounded-md gap-1 text-xs text-gray-600 hover:text-gray-700 hover:bg-gray-100 transition-all">
        View more <InfoIcon className="size-3" />
      </PopoverTrigger>

      <PopoverContent className="w-full">
        <EventDetails {...props} />
      </PopoverContent>
    </Popover>
  );
}
