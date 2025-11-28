import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import { HomeEvents } from "@/entities/events/ui/node-details-events-homepage";

interface EventsWidgetProps {
  className?: string;
}

export const EventsWidget = ({ className }: EventsWidgetProps) => {
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

      <HomeEvents />
    </HomeCard>
  );
};
