import * as R from "remeda";

import {
  SORT_DIRECTION,
  type Sort,
  type SortDirection,
  type SortField,
  type SortToken,
} from "@/entities/nodes/sort/domain/model/sort";

export function parseSortToken(token: string): Sort {
  const segments = token.split("__");
  const dir = R.last(segments);
  const field = R.dropLast(segments, 1).join("__");
  const isDirection = dir === "asc" || dir === "desc";

  if (!field || !isDirection) {
    return { field: token as SortField, direction: SORT_DIRECTION.ASC };
  }

  return {
    field: field as SortField,
    direction: dir === "desc" ? SORT_DIRECTION.DESC : SORT_DIRECTION.ASC,
  };
}

export function serializeSortToken(sort: Sort): SortToken {
  return `${sort.field}__${sort.direction.toLowerCase() as Lowercase<SortDirection>}`;
}
