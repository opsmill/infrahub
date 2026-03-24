import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

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
    <Card className={classNames("overflow-x-hidden p-0", className)} data-testid="activities-panel">
      <CardWithBorder.Title className="border-gray-200 border-b">Activities</CardWithBorder.Title>
      <NodeEvents objectKind={objectKind} objectId={objectId} />
    </Card>
  );
}
