import { ObjectDetails } from "@/entities/nodes/object/ui/object-details/object-details";
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";

export function Component() {
  const { objectSchema, objectData, permission } = useObjectDetailsOutlet();
  return (
    <ObjectDetails objectSchema={objectSchema} objectData={objectData} permission={permission} />
  );
}
