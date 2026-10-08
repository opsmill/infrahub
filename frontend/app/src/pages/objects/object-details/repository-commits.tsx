import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { getRepositoryLocation } from "@/entities/repository/domain/rules/get-repository-location";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export function Component() {
  const { objectData, objectSchema, permission } = useObjectDetailsOutlet();

  return (
    <RepositoryCommitsManager
      repositoryId={objectData.id}
      repositoryLocation={getRepositoryLocation(objectData)}
      isReadOnly={isOfKind(READONLY_REPOSITORY_KIND, objectSchema)}
      updatePermission={permission.update}
    />
  );
}
