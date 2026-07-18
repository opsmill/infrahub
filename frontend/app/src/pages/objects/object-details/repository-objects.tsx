import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { RepositoryObjectsManager } from "@/entities/repository/ui/repository-objects-manager";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  return <RepositoryObjectsManager parentNodeId={objectData.id} />;
}
