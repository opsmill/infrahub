import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";

import { HomeEvents } from "@/entities/events/ui/node-details-events-homepage";
import { HomeCard } from "@/entities/homepage/ui/home-card";

interface EventsWidgetProps {
  className?: string;
}

export const EventsWidget = ({ className }: EventsWidgetProps) => {
  return (
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon={"mdi:file-replace-outline"} /> Recent Activities
        </Row>

        <HomeCard.Link to={constructPath("/activities")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <HomeEvents />
    </HomeCard>
  );
};
