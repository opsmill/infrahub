import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { partitionFieldsByBranchSupport } from "@/entities/repository/domain/rules/partition-fields-by-branch-support";
import { RepositoryBranchesCard } from "@/entities/repository/ui/repository-branches-card/repository-branches-card";
import { RepositoryDetailsCard } from "@/entities/repository/ui/repository-details-card";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface RepositoryObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
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
      <RepositoryDetailsCard
        title="Details"
        testId="repository-details"
        objectSchema={{ ...objectSchema, ...repositoryWide }}
        objectData={objectData}
        permission={permission}
      />

      <RepositoryDetailsCard
        title="On this branch"
        caption={currentBranch.name}
        testId="repository-branch-details"
        objectSchema={{ ...objectSchema, ...branchScoped }}
        objectData={objectData}
        permission={permission}
      />

      <RepositoryBranchesCard repositoryId={objectData.id} schema={objectSchema} />
    </>
  );
}
