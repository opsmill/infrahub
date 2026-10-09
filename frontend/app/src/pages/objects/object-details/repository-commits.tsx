import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { getRepositoryLocation } from "@/entities/repository/domain/rules/get-repository-location";
import { isReadOnlyRepository } from "@/entities/repository/domain/rules/is-read-only-repository";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";

export function Component() {
  const { objectData, objectSchema, permission } = useObjectDetailsOutlet();

  return (
    <RepositoryCommitsManager
      repositoryId={objectData.id}
      repositoryLocation={getRepositoryLocation(objectData)}
      remoteCheck={
        isReadOnlyRepository(objectSchema)
          ? { objectKind: objectSchema.kind, updatePermission: permission.update }
          : null
      }
    />
  );
}
