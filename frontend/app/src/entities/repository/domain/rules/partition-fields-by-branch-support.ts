import type { components } from "@/shared/api/rest/types.generated";

import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

type BranchSupportType = components["schemas"]["BranchSupportType"];

export type FieldSet = {
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
};

export type BranchSupportPartition = {
  repositoryWide: FieldSet;
  branchScoped: FieldSet;
};

const BRANCH_SCOPED_SUPPORT: BranchSupportType[] = ["aware", "local"];

function isBranchScoped(
  fieldBranch: BranchSupportType | null | undefined,
  nodeBranch: BranchSupportType
): boolean {
  return BRANCH_SCOPED_SUPPORT.includes(fieldBranch ?? nodeBranch);
}

export function partitionFieldsByBranchSupport(schema: ModelSchema): BranchSupportPartition {
  const nodeBranch = schema.branch;
  const attributes = schema.attributes ?? [];
  const relationships = schema.relationships ?? [];

  return {
    repositoryWide: {
      attributes: attributes.filter((attribute) => !isBranchScoped(attribute.branch, nodeBranch)),
      relationships: relationships.filter(
        (relationship) => !isBranchScoped(relationship.branch, nodeBranch)
      ),
    },
    branchScoped: {
      attributes: attributes.filter((attribute) => isBranchScoped(attribute.branch, nodeBranch)),
      relationships: relationships.filter((relationship) =>
        isBranchScoped(relationship.branch, nodeBranch)
      ),
    },
  };
}
