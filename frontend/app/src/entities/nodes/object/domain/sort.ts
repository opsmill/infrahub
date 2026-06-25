import * as R from "remeda";

import {
  getSortableFields,
  type SortDirection,
  type SortFieldKey,
} from "@/entities/nodes/object/domain/sortable-field";
import type { ModelSchema } from "@/entities/schema/types";

/** Lowercase `field__direction` token, e.g. `name__value__asc`; the URL and REST `order_by` form. */
export type SortToken = `${SortFieldKey}__${Lowercase<SortDirection>}`;

export interface Sort {
  field: SortFieldKey;
  direction: SortDirection;
}

const DIRECTION_SUFFIX = /__(asc|desc)$/;

export function getSortField(sort: string): SortFieldKey {
  return sort.replace(DIRECTION_SUFFIX, "") as SortFieldKey;
}

export function getSortDirection(sort: string): SortDirection {
  return sort.endsWith("__desc") ? "DESC" : "ASC";
}

export function formatSort(field: SortFieldKey, direction: SortDirection): SortToken {
  return `${field}__${direction.toLowerCase() as Lowercase<SortDirection>}`;
}

export function parseSort(token: string): Sort {
  return { field: getSortField(token), direction: getSortDirection(token) };
}

/** Sortable, field-deduplicated entries (first wins), or `null` when none remain. */
export function getValidSort(
  sorts: Sort[] | null | undefined,
  sortableKeys: ReadonlySet<SortFieldKey>
): Sort[] | null {
  const valid = R.pipe(
    sorts ?? [],
    R.filter((sort) => sortableKeys.has(sort.field)),
    R.uniqueBy((sort) => sort.field)
  );

  return valid.length > 0 ? valid : null;
}

export function getSchemaDefaultSort(schema: ModelSchema): Sort[] | null {
  const sortableKeys = new Set(getSortableFields(schema).map((field) => field.field));
  return getValidSort(schema.order_by?.map(parseSort), sortableKeys);
}

/** Order-sensitive: position encodes primary → secondary precedence. */
export function sortsEqual(a: Sort[], b: Sort[]): boolean {
  return (
    a.length === b.length &&
    a.every((sort, i) => sort.field === b[i]?.field && sort.direction === b[i]?.direction)
  );
}
