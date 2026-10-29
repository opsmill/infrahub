import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { getRepositoryInternalStatus } from "@/entities/repository/domain/rules/get-repository-internal-status";
import { getRepositoryLocation } from "@/entities/repository/domain/rules/get-repository-location";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";

export function Component() {
  const { objectData, objectSchema, permission } = useObjectDetailsOutlet();

  return (
    <RepositoryCommitsManager
      repositoryId={objectData.id}
      repositoryKind={objectSchema.kind}
      repositoryName={getNodeLabel(objectData)}
      repositoryInternalStatus={getRepositoryInternalStatus(objectData)}
      repositoryLocation={getRepositoryLocation(objectData)}
      updatePermission={permission.update}
    />
  );
}
