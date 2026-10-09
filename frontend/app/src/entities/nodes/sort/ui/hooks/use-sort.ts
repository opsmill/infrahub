import { createParser, parseAsArrayOf, parseAsInteger, useQueryState } from "nuqs";

import {
  SCOPELESS_PAGE_KEY,
  useFilterScope,
} from "@/entities/nodes/filters/ui/filter-scope-context";
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
  /** Pass null (or []) to clear the custom sort and restore the default order. */
  setCustomSort: (next: Sort[] | null) => void;
  /** The schema's order_by, or null when it defines none. */
  defaultSort: Sort[] | null;
  /** The sort effectively applied: custom sort, else schema default, else empty. */
  appliedSort: Sort[];
};

export const useSort: UseSort = (schema) => {
  const { sortKey, pageKey } = useFilterScope();
  const [sortInQsp, setSortInQsp] = useQueryState(
    sortKey,
    parseAsArrayOf(sortParser).withOptions({ history: "push" })
  );
  const [, setPage] = useQueryState(pageKey ?? SCOPELESS_PAGE_KEY, parseAsInteger);

  const validSort = getValidSorts(sortInQsp ?? [], schema);

  const customSort = validSort.length > 0 ? validSort : null;
  const setCustomSort = (next: Sort[] | null) => {
    setSortInQsp(next && next.length > 0 ? next : null);

    // The page was chosen against the old order, so its window says nothing about the new one.
    if (pageKey) setPage(null);
  };
  const defaultSort = getSchemaDefaultSort(schema);
  const appliedSort = customSort ?? defaultSort ?? [];

  return { customSort, setCustomSort, defaultSort, appliedSort };
};
