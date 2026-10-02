import type { InfrahubNodeMetadataOrder } from "@/shared/api/graphql/generated/types";

import { type Filter, SEARCH_ANY_FILTER } from "@/entities/nodes/filters/domain/model/filter";
import {
  type NodeMetadataSortField,
  SORT_DIRECTION,
  type Sort,
} from "@/entities/nodes/sort/domain/model/sort";
import type { GetRepositoryBranchStatusFromApiParams } from "@/entities/repository/api/get-repository-branch-status-from-api";
import { isFilterableBranchStatus } from "@/entities/repository/ui/repository-branches-card/branch-row-fields";

export type RepositoryBranchArguments = Pick<
  GetRepositoryBranchStatusFromApiParams,
  "name__value" | "partial_match" | "status__value" | "order"
>;

const NAME_FILTER = "name__value";
const STATUS_FILTER = "status__value";
const CREATED_AT_SORT_FIELD: NodeMetadataSortField = "node_metadata__created_at";
const UPDATED_AT_SORT_FIELD: NodeMetadataSortField = "node_metadata__updated_at";

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

// The contract rejects an order naming both timestamps, so only the first sort key reaches the
// request — it is the one that decides the order on screen, the rest only break its ties.
function toOrderArgument(sorts: Sort[]): RepositoryBranchArguments {
  const primary = sorts.find(
    (sort) => sort.field === CREATED_AT_SORT_FIELD || sort.field === UPDATED_AT_SORT_FIELD
  );

  if (!primary) return {};

  const direction = primary.direction === SORT_DIRECTION.DESC ? "DESC" : "ASC";
  const nodeMetadata: InfrahubNodeMetadataOrder =
    primary.field === CREATED_AT_SORT_FIELD ? { created_at: direction } : { updated_at: direction };

  return { order: { node_metadata: nodeMetadata } };
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

/**
 * Whether the row set the server answered with was narrowed by anything the user asked for. Derived
 * from the arguments themselves, so a filter the contract has no argument for cannot make an empty
 * result claim it was filtered.
 */
export function hasRepositoryBranchFilters(filters: Filter[]): boolean {
  const { name__value, status__value } = toRepositoryBranchArguments(filters, []);

  return name__value !== undefined || status__value !== undefined;
}
