import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { PROPOSED_CHANGE_DEFAULT_SORT } from "@/entities/proposed-changes/domain/model/proposed-change-sort";

/** The order the list actually queries: what the user chose, else the list default. */
export function computeProposedChangeSort(sort: Sort[]): Sort[] {
  return sort.length > 0 ? sort : [PROPOSED_CHANGE_DEFAULT_SORT];
}
