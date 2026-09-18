import { BranchStatus } from "@/shared/api/graphql/generated/types";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import type { FilterDefinition } from "@/entities/nodes/object/domain/model/filter-definition";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

// A repository's branches never come back as `MERGED` or `DELETING`, so offering either would only
// ever produce an empty result.
export const FILTERABLE_BRANCH_STATUSES = [
  BranchStatus.OPEN,
  BranchStatus.NEED_REBASE,
  BranchStatus.NEED_UPGRADE_REBASE,
  BranchStatus.MERGING,
  BranchStatus.MERGE_FAILED,
] as const;

export type FilterableBranchStatus = (typeof FILTERABLE_BRANCH_STATUSES)[number];

export function isFilterableBranchStatus(value: unknown): value is FilterableBranchStatus {
  return FILTERABLE_BRANCH_STATUSES.some((status) => status === value);
}

const BRANCH_STATUS_FIELD_SCHEMA: AttributeSchema = {
  ...BRANCH_FIELD_SCHEMAS.status,
  enum: [...FILTERABLE_BRANCH_STATUSES],
};

// Branch name and branch status are the only two the contract can narrow on; a row's sync status,
// commit and ref have no filter argument at all.
export const BRANCH_ROW_FILTER_DEFINITIONS: FilterDefinition[] = [
  { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.name },
  { type: "attribute", schema: BRANCH_STATUS_FIELD_SCHEMA },
];

export const BRANCH_ROW_FILTER_DEFINITIONS_BY_NAME: Record<string, FilterDefinition> = {
  [BRANCH_FIELD_SCHEMAS.name.name]: { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.name },
  [BRANCH_STATUS_FIELD_SCHEMA.name]: { type: "attribute", schema: BRANCH_STATUS_FIELD_SCHEMA },
};

// The contract orders by branch node metadata only, so the schema the sort UI reads declares no
// sortable field of its own and is left with the two metadata timestamps every node carries.
export const BRANCH_ROW_SORT_SCHEMA: ModelSchema = {
  kind: "InfrahubRepositoryBranchStatus",
  name: "Branch",
  namespace: "Infrahub",
  label: "Branches",
  branch: "agnostic",
  state: "present",
  generate_profile: false,
  generate_template: false,
  attributes: [],
  relationships: [],
};
