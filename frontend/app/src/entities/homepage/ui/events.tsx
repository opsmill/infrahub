import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { HomeCard } from "@/shared/components/ui/home-card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { classNames } from "@/shared/utils/common";

import { NodeEvents } from "@/entities/events/ui/node-details-events";

interface EventsProps {
  className?: string;
}

const MAX_EVENTS = 10;

export const Events = ({ className }: EventsProps) => {
  return (
    <HomeCard className={classNames("flex flex-col", className)}>
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:file-replace-outline"} /> Recent Activities
        </span>

        <HomeCard.Link to={constructPath("/activities")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <ScrollArea>
        <NodeEvents maxEvent={MAX_EVENTS} />
      </ScrollArea>
    </HomeCard>
  );
};
