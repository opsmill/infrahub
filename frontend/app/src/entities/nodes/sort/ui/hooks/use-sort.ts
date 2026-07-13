import { createParser, parseAsArrayOf, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { getValidSorts } from "@/entities/nodes/sort/domain/rules/get-valid-sorts";
import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

const sortParser = createParser({
  parse: parseSortToken,
  serialize: serializeSortToken,
});

type UseSort = (schema: ModelSchema) => {
  sort: Sort[] | null;
  setSort: (next: Sort[]) => void;
};

export const useSort: UseSort = (schema) => {
  const [sortInQsp, setSortInQsp] = useQueryState(
    QSP.SORT,
    parseAsArrayOf(sortParser).withOptions({ history: "push" })
  );

  const validSort = getValidSorts(sortInQsp ?? [], schema);

  const sort = validSort.length > 0 ? validSort : null;
  const setSort = (next: Sort[]) => setSortInQsp(next.length > 0 ? next : null);

  return { sort, setSort };
};
