import { InfoIcon } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import type { EventType } from "@/entities/events/types";

import { EventDetails } from "./event-details";

export function EventDetailsPopover(props: EventType) {
  return (
    <Popover>
      <PopoverTrigger className="flex items-center gap-1 rounded-md px-1 py-0.5 text-gray-600 text-xs transition-all hover:bg-gray-100 hover:text-gray-700">
        View more <InfoIcon className="size-3" />
      </PopoverTrigger>

      <PopoverContent className="max-h-64 w-full overflow-scroll">
        <ScrollArea scrollY>
          <EventDetails {...props} />
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
