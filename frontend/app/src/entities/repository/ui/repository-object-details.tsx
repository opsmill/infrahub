import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import {
  type FieldSet,
  partitionFieldsByBranchSupport,
} from "@/entities/repository/domain/rules/partition-fields-by-branch-support";
import { useRefreshAfterRepositoryRun } from "@/entities/repository/ui/hooks/use-refresh-after-repository-run";
import { RepositoryActivityCard } from "@/entities/repository/ui/repository-activity-card/repository-activity-card";
import { RepositoryBranchesCard } from "@/entities/repository/ui/repository-branches-card/repository-branches-card";
import { RepositoryPushToRemoteCard } from "@/entities/repository/ui/repository-push-to-remote-card";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

interface RepositoryObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

function hasFields({ attributes, relationships }: FieldSet): boolean {
  return attributes.length > 0 || relationships.length > 0;
}

export function RepositoryObjectDetails({
  objectSchema,
  objectData,
  permission,
}: RepositoryObjectDetailsProps) {
  const { currentBranch } = useCurrentBranch();
  const { repositoryWide, branchScoped } = partitionFieldsByBranchSupport(objectSchema);
  // This page shows the cards a finished run changes, so it is the one that refreshes them.
  useRefreshAfterRepositoryRun({ repositoryId: objectData.id });

  return (
    <>
      {hasFields(repositoryWide) && (
        <ObjectDetailsCard
          objectSchema={{ ...objectSchema, ...repositoryWide }}
          objectData={objectData}
          permission={permission}
        />
      )}

      {hasFields(branchScoped) && (
        <ObjectDetailsCard
          title="On this branch"
          caption={currentBranch.name}
          objectSchema={{ ...objectSchema, ...branchScoped }}
          objectData={objectData}
          permission={permission}
        />
      )}

      <RepositoryBranchesCard repositoryId={objectData.id} schema={objectSchema} />

      <RepositoryActivityCard repositoryId={objectData.id} />

      {isOfKind(REPOSITORY_KIND, objectSchema) && (
        <RepositoryPushToRemoteCard repositoryId={objectData.id} />
      )}
    </>
  );
}
