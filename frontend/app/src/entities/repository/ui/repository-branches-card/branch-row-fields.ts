import { BranchStatus } from "@/shared/api/graphql/generated/types";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import type { FilterDefinition } from "@/entities/nodes/object/domain/model/filter-definition";
import { getFilterDefinitionName } from "@/entities/nodes/object/domain/rules/filter-definition";
import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
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

/** The one key the search box, the filter form and the column menu all write. */
export const BRANCH_NAME_FILTER = "name__value";

// The server refuses an order naming both timestamps, so offering a second key would promise an
// ordering the request cannot carry.
export const BRANCH_ROW_MAX_SORTS = 1;

export function isFilterableBranchStatus(value: unknown): value is FilterableBranchStatus {
  return FILTERABLE_BRANCH_STATUSES.some((status) => status === value);
}

const BRANCH_STATUS_FIELD_SCHEMA: AttributeSchema = {
  ...BRANCH_FIELD_SCHEMAS.status,
  enum: [...FILTERABLE_BRANCH_STATUSES],
};

// Only the two fields the query narrows on and this card chooses to offer.
export const BRANCH_ROW_FILTER_DEFINITIONS: FilterDefinition[] = [
  { type: "attribute", schema: BRANCH_FIELD_SCHEMAS.name },
  { type: "attribute", schema: BRANCH_STATUS_FIELD_SCHEMA },
];

export const BRANCH_ROW_FILTER_DEFINITIONS_BY_NAME: Record<string, FilterDefinition> =
  Object.fromEntries(
    BRANCH_ROW_FILTER_DEFINITIONS.map((definition) => [
      getFilterDefinitionName(definition),
      definition,
    ])
  );

// Branch name and branch status are the only two fields this card filters on, so an emptiness
// condition would leave the request unnarrowed while the tag claimed otherwise.
export const BRANCH_ROW_FILTER_CONDITIONS: readonly FilterCondition[] = [FILTER_CONDITION.CONTAINS];

// The query orders by branch node metadata only, so the schema the sort UI reads declares no
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
