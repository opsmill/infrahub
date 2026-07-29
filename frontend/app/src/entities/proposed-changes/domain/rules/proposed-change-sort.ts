import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { PROPOSED_CHANGE_DEFAULT_SORT } from "@/entities/proposed-changes/domain/model/proposed-change-sort";

function isSameSort(one: Sort, other: Sort): boolean {
  return one.field === other.field && one.direction === other.direction;
}

/** The order the list actually queries: what the user chose, else the list default. */
export function computeProposedChangeSort(sort: Sort[]): Sort[] {
  return sort.length > 0 ? sort : [PROPOSED_CHANGE_DEFAULT_SORT];
}

/**
 * Whether an applied order is exactly the one a menu option offers. A sort can also arrive from the
 * URL (`?sort=name__value__asc`, or several keys at once); those are honoured, and no option claims
 * to be the applied one.
 */
export function isProposedChangeSortApplied(option: Sort, sort: Sort[]): boolean {
  const [applied] = sort;

  return sort.length === 1 && !!applied && isSameSort(applied, option);
}

/**
 * Whether rows should surface their update date: the primary sort key drives a row's position, so
 * only that key decides which date explains the ordering.
 */
export function isProposedChangeSortedByUpdatedAt(sort: Sort[]): boolean {
  return sort[0]?.field === "node_metadata__updated_at";
}

/** Picking the default order clears the URL param rather than spelling out the default in it. */
export function isProposedChangeDefaultSort(sort: Sort): boolean {
  return isSameSort(sort, PROPOSED_CHANGE_DEFAULT_SORT);
}
