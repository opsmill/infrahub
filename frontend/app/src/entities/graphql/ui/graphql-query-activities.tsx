import { Card, CardWithBorder } from "@/shared/components/ui/card";

import { NodeEvents } from "@/entities/events/ui/node-details-events";

export const GraphqlQueryActivities = ({ id }: { id: string }) => {
  return (
    <Card className="p-0 overflow-x-hidden">
      <CardWithBorder.Title>Activities</CardWithBorder.Title>

      <NodeEvents objectId={id} />
    </Card>
  );
};
