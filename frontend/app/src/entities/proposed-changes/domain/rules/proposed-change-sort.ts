import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { PROPOSED_CHANGE_DEFAULT_SORT } from "@/entities/proposed-changes/domain/model/proposed-change-sort";

/** The order the list actually queries: what the user chose, else the list default. */
export function computeProposedChangeSort(sort: Sort[]): Sort[] {
  return sort.length > 0 ? sort : [PROPOSED_CHANGE_DEFAULT_SORT];
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
  return (
    sort.field === PROPOSED_CHANGE_DEFAULT_SORT.field &&
    sort.direction === PROPOSED_CHANGE_DEFAULT_SORT.direction
  );
}
