import { Card, CardHeader } from "@infrahub/ui";

import type { EventType } from "@/entities/events/types";

import { EventDetails } from "./event-details";
import { NodeEvents } from "./node-details-events";

export interface GlobalEventDetailsProps {
  eventNode: EventType;
}

export const GlobalEventDetails = ({ eventNode }: GlobalEventDetailsProps) => {
  return (
    <div className="flex items-start gap-2 p-2">
      <Card className="flex-1">
        <CardHeader>Details</CardHeader>
        <EventDetails {...eventNode} />
      </Card>

      {eventNode.has_children && (
        <Card className="flex-1">
          <CardHeader>Sub activities</CardHeader>
          <NodeEvents parentId={eventNode.id} />
        </Card>
      )}
    </div>
  );
};
