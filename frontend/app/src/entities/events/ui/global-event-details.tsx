import { Card, CardWithBorder } from "@/shared/components/ui/card";

import { EventType } from "@/entities/events/types";

import { EventDetails } from "./event-details";
import { NodeEvents } from "./node-details-events";

export interface GlobalEventDetailsProps {
  eventNode: EventType;
}

export const GlobalEventDetails = ({ eventNode }: GlobalEventDetailsProps) => {
  return (
    <div className="p-2 flex items-start gap-2">
      <Card className="p-0 flex-1">
        <CardWithBorder.Title>Details</CardWithBorder.Title>
        <EventDetails {...eventNode} />
      </Card>

      {eventNode.has_children && (
        <Card className="p-0 flex-1">
          <CardWithBorder.Title>Sub activities</CardWithBorder.Title>
          <NodeEvents parentId={eventNode.id} />
        </Card>
      )}
    </div>
  );
};
