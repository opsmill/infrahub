import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { RackElevationView } from "@/entities/rack-elevation/ui/rack-elevation-view";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();

  return <RackElevationView rackId={objectData.id} />;
}
