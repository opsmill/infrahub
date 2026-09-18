import { type Filter, SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import { getFilterDefinitionName } from "@/entities/nodes/object/domain/rules/filter-definition";
import {
  NODE_METADATA_SORT_FIELDS,
  SORT_DIRECTION,
  type Sort,
} from "@/entities/nodes/sort/domain/model/sort";
import type { GetRepositoryBranchStatusFromApiParams } from "@/entities/repository/api/get-repository-branch-status-from-api";
import {
  BRANCH_ROW_FILTER_DEFINITIONS,
  isFilterableBranchStatus,
} from "@/entities/repository/ui/repository-branches-card/branch-row-fields";

export type RepositoryBranchArguments = Pick<
  GetRepositoryBranchStatusFromApiParams,
  "name__value" | "partial_match" | "status__value" | "order"
>;

const NAME_FILTER = "name__value";
const STATUS_FILTER = "status__value";
const [CREATED_AT_SORT_FIELD, UPDATED_AT_SORT_FIELD] = NODE_METADATA_SORT_FIELDS;

function findFilterValue(filters: Filter[], name: string): unknown {
  return filters.find((filter) => filter.name === name)?.value;
}

function toStringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

// The contract narrows names through `name__value`, so the toolbar's free-text search reaches it
// too; an explicit name filter is the more specific of the two and wins.
function toNameArguments(filters: Filter[]): RepositoryBranchArguments {
  const fragment =
    toStringValue(findFilterValue(filters, NAME_FILTER)) ??
    toStringValue(findFilterValue(filters, SEARCH_ANY_FILTER));

  if (fragment === undefined) return {};

  return { name__value: fragment, partial_match: true };
}

function toStatusArguments(filters: Filter[]): RepositoryBranchArguments {
  const status = findFilterValue(filters, STATUS_FILTER);

  return isFilterableBranchStatus(status) ? { status__value: status } : {};
}

function toOrderArgument(sorts: Sort[]): RepositoryBranchArguments {
  for (const sort of sorts) {
    const direction = sort.direction === SORT_DIRECTION.DESC ? "DESC" : "ASC";

    if (sort.field === CREATED_AT_SORT_FIELD) {
      return { order: { node_metadata: { created_at: direction } } };
    }

    if (sort.field === UPDATED_AT_SORT_FIELD) {
      return { order: { node_metadata: { updated_at: direction } } };
    }
  }

  return {};
}

/** Every filter the toolbar can produce that the contract is able to apply, plus the order. */
export function toRepositoryBranchArguments(
  filters: Filter[],
  sorts: Sort[]
): RepositoryBranchArguments {
  return {
    ...toNameArguments(filters),
    ...toStatusArguments(filters),
    ...toOrderArgument(sorts),
  };
}

/** Whether the row set the server answered with was narrowed by anything the user asked for. */
export function hasRepositoryBranchFilters(filters: Filter[]): boolean {
  return filters.some(
    (filter) =>
      filter.name === SEARCH_ANY_FILTER ||
      BRANCH_ROW_FILTER_DEFINITIONS.some((definition) =>
        isFieldFiltered(filter, getFilterDefinitionName(definition))
      )
  );
}
