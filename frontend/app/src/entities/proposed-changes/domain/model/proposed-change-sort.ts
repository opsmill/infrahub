import {
  type NodeMetadataSortField,
  SORT_DIRECTION,
  type Sort,
} from "@/entities/nodes/sort/domain/model/sort";

/** A date sort the proposed-changes list offers as a one-click option. */
export interface ProposedChangeSortOption {
  id: string;
  label: string;
  sort: Sort & { field: NodeMetadataSortField };
}

/**
 * Order applied when the user hasn't picked one. The proposed-change schema declares no default
 * order, so the list owns one — unordered, the backend falls back to node-uuid order and buries the
 * most recent proposed changes.
 */
export const PROPOSED_CHANGE_DEFAULT_SORT: ProposedChangeSortOption["sort"] = {
  field: "node_metadata__created_at",
  direction: SORT_DIRECTION.DESC,
};

/** Wording follows the sort menu on GitHub pull requests, which users arrive here already knowing. */
export const PROPOSED_CHANGE_SORT_OPTIONS: ProposedChangeSortOption[] = [
  {
    id: "newest",
    label: "Newest",
    sort: PROPOSED_CHANGE_DEFAULT_SORT,
  },
  {
    id: "oldest",
    label: "Oldest",
    sort: { field: "node_metadata__created_at", direction: SORT_DIRECTION.ASC },
  },
  {
    id: "recently-updated",
    label: "Recently updated",
    sort: { field: "node_metadata__updated_at", direction: SORT_DIRECTION.DESC },
  },
  {
    id: "least-recently-updated",
    label: "Least recently updated",
    sort: { field: "node_metadata__updated_at", direction: SORT_DIRECTION.ASC },
  },
];
