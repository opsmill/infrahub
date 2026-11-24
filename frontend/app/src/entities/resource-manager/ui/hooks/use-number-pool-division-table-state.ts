import { createParser, debounce, parseAsString, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

export interface NumberPoolDivisionSort {
  by: string;
  direction: "ascending" | "descending";
}

export const NUMBER_POOL_DIVISION_SORT_BY_USAGE = "usage";

const DEFAULT_SORT: NumberPoolDivisionSort = {
  by: NUMBER_POOL_DIVISION_SORT_BY_USAGE,
  direction: "descending",
};

const parseAsDivisionSort = createParser<NumberPoolDivisionSort>({
  parse: (value) => {
    const separator = value.lastIndexOf(":");
    if (separator <= 0) return null;
    const direction = value.slice(separator + 1);
    if (direction !== "asc" && direction !== "desc") return null;
    return {
      by: value.slice(0, separator),
      direction: direction === "asc" ? "ascending" : "descending",
    };
  },
  serialize: ({ by, direction }) => `${by}:${direction === "ascending" ? "asc" : "desc"}`,
  eq: (a, b) => a.by === b.by && a.direction === b.direction,
});

export function useNumberPoolDivisionTableState() {
  const [search, setSearch] = useQueryState(
    QSP.ALLOCATION_SCOPE_SEARCH,
    parseAsString.withDefault("").withOptions({ limitUrlUpdates: debounce(300) })
  );
  const [sort, setSort] = useQueryState(
    QSP.ALLOCATION_SCOPE_SORT,
    parseAsDivisionSort.withDefault(DEFAULT_SORT)
  );

  return [
    { search, sort },
    { setSearch, setSort },
  ] as const;
}
