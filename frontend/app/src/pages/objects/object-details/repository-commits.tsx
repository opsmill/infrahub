import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { getRepositoryLocation } from "@/entities/repository/domain/rules/get-repository-location";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();

  return (
    <RepositoryCommitsManager
      repositoryId={objectData.id}
      repositoryLocation={getRepositoryLocation(objectData)}
    />
  );
}
