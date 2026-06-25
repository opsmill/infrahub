import { createParser, parseAsArrayOf, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import {
  formatSort,
  getSchemaDefaultSort,
  getValidSort,
  parseSort,
  type Sort,
  sortsEqual,
} from "@/entities/nodes/object/domain/sort";
import { getSortableFields } from "@/entities/nodes/object/domain/sortable-field";
import type { ModelSchema } from "@/entities/schema/types";

const sortParser = createParser({
  parse: (token: string): Sort => parseSort(token),
  serialize: (sort: Sort): string => formatSort(sort.field, sort.direction),
});

/**
 * `?sort` as structured {@link Sort} entries. `null` means "on the schema default": unsortable
 * entries drop from the result but stay in the URL (so they revive on a schema change), and
 * `setSort` removes the param when given the default or an empty list, re-tracking the live default.
 */
export function useSort(schema: ModelSchema): [Sort[] | null, (next: Sort[]) => void] {
  const [rawSort, setRawSort] = useQueryState(
    QSP.SORT,
    parseAsArrayOf(sortParser).withOptions({ history: "push" })
  );

  const sortableKeys = new Set(getSortableFields(schema).map((field) => field.field));
  const schemaDefault = getSchemaDefaultSort(schema) ?? [];

  const sort = getValidSort(rawSort, sortableKeys);
  const setSort = (next: Sort[]) =>
    setRawSort(next.length > 0 && !sortsEqual(next, schemaDefault) ? next : null);

  return [sort, setSort];
}
