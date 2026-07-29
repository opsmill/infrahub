import {
  type NodeMetadataSortField,
  SORT_DIRECTION,
  type Sort,
  type SortDirection,
} from "@/entities/nodes/sort/domain/model/sort";

/** The date orders the list offers, spelled as the tokens the URL and the sort menu key them by. */
export type ProposedChangeSortToken = `${NodeMetadataSortField}__${Lowercase<SortDirection>}`;

/**
 * Order applied when the user hasn't picked one. The proposed-change schema declares no default
 * order, so the list owns one — unordered, the backend falls back to node-uuid order and buries the
 * most recent proposed changes.
 */
export const PROPOSED_CHANGE_DEFAULT_SORT: Sort & { field: NodeMetadataSortField } = {
  field: "node_metadata__created_at",
  direction: SORT_DIRECTION.DESC,
};
