import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import type { Permission } from "@/entities/permission/domain/model/permission";
import {
  type FieldSet,
  partitionFieldsByBranchSupport,
} from "@/entities/repository/domain/rules/partition-fields-by-branch-support";
import { RepositoryBranchesCard } from "@/entities/repository/ui/repository-branches-card/repository-branches-card";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

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
    </>
  );
}
