import { Card, CardWithBorder } from "@/shared/components/ui/card";

import type { EventType } from "@/entities/events/types";

import { EventDetails } from "./event-details";
import { NodeEvents } from "./node-details-events";

export interface GlobalEventDetailsProps {
  eventNode: EventType;
}

export const GlobalEventDetails = ({ eventNode }: GlobalEventDetailsProps) => {
  return (
    <div className="flex items-start gap-2 p-2">
      <Card className="flex-1 p-0">
        <CardWithBorder.Title>Details</CardWithBorder.Title>
        <EventDetails {...eventNode} />
      </Card>

      {eventNode.has_children && (
        <Card className="flex-1 p-0">
          <CardWithBorder.Title>Sub activities</CardWithBorder.Title>
          <NodeEvents parentId={eventNode.id} />
        </Card>
      )}
    </div>
  );
};
