import { EventType } from "@/entities/events/types";
import { EventDetails } from "@/entities/events/ui/event-card";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { InfoIcon } from "lucide-react";

export function EventDetailsPopover(props: EventType) {
  return (
    <Popover>
      <PopoverTrigger className="flex items-center gap-1 text-xs text-gray-600">
        View all <InfoIcon className="size-3" />
      </PopoverTrigger>

      <PopoverContent className="w-full">
        <EventDetails {...props} />
      </PopoverContent>
    </Popover>
  );
}
