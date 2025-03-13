import Content from "@/shared/components/layout/content";
import { CardWithBorder } from "@/shared/components/ui/card";
import { EventDetails } from "./event-card";
import { NodeEvents } from "./node-details-events";
import { EventType } from "@/entities/events/types";

export interface GlobalEventDetailsProps {
  eventNode: EventType;
}

export const GlobalEventDetails = ({ eventNode }: GlobalEventDetailsProps) => {
  return (
    <Content.CardContent className="p-2">
      <div className="flex items-start gap-2">
        <CardWithBorder className="p-0 border-0 flex-1">
          <CardWithBorder.Title>Details</CardWithBorder.Title>
          <EventDetails {...eventNode} />
        </CardWithBorder>

        {eventNode?.has_children && (
          <CardWithBorder className="p-0 border-0 flex-1">
            <CardWithBorder.Title>Sub activities</CardWithBorder.Title>
            <NodeEvents parentId={eventNode.id} />
          </CardWithBorder>
        )}
      </div>
    </Content.CardContent>
  );
};
