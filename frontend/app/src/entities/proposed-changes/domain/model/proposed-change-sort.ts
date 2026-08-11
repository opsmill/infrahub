import { SORT_DIRECTION, type Sort } from "@/entities/nodes/sort/domain/model/sort";

export const PROPOSED_CHANGE_DEFAULT_SORT: Sort = {
  field: "node_metadata__created_at",
  direction: SORT_DIRECTION.DESC,
};
