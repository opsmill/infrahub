import { Card, CardHeader } from "@infrahub/ui";

import { NodeEvents } from "@/entities/events/ui/node-details-events";

interface ObjectActivitiesCardProps {
  objectKind: string;
  objectId: string;
  className?: string;
}

export function ObjectActivitiesCard({
  objectKind,
  objectId,
  className,
}: ObjectActivitiesCardProps) {
  return (
    <Card className={className} data-testid="activities-panel">
      <CardHeader>Activities</CardHeader>
      <NodeEvents objectKind={objectKind} objectId={objectId} />
    </Card>
  );
}
