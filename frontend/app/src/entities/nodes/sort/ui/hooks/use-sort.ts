import { createParser, parseAsArrayOf, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { getSchemaDefaultSort } from "@/entities/nodes/sort/domain/rules/get-schema-default-sort";
import { getValidSorts } from "@/entities/nodes/sort/domain/rules/get-valid-sorts";
import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

const sortParser = createParser({
  parse: parseSortToken,
  serialize: serializeSortToken,
});

type UseSort = (schema: ModelSchema) => {
  /** The sort the user explicitly chose (URL state), or null when they haven't customized. */
  customSort: Sort[] | null;
  setCustomSort: (next: Sort[]) => void;
  /** The schema's order_by, or null when it defines none. */
  defaultSort: Sort[] | null;
  /** The sort effectively applied: custom sort, else schema default, else empty. */
  appliedSort: Sort[];
};

export const useSort: UseSort = (schema) => {
  const [sortInQsp, setSortInQsp] = useQueryState(
    QSP.SORT,
    parseAsArrayOf(sortParser).withOptions({ history: "push" })
  );

  const validSort = getValidSorts(sortInQsp ?? [], schema);

  const customSort = validSort.length > 0 ? validSort : null;
  const setCustomSort = (next: Sort[]) => setSortInQsp(next.length > 0 ? next : null);
  const defaultSort = getSchemaDefaultSort(schema);
  const appliedSort = customSort ?? defaultSort ?? [];

  return { customSort, setCustomSort, defaultSort, appliedSort };
};
