import type { SearchResultsFromApiParams } from "@/entities/search-results/api/search-results";

export const searchResultsQueryKeys = {
  all: ({
    branchName,
    atDate,
    search,
  }: Pick<SearchResultsFromApiParams, "branchName" | "atDate" | "search">) => [
    branchName,
    atDate,
    "search-results",
    search,
  ],
  paginated: (params: SearchResultsFromApiParams) => [
    params.branchName,
    params.atDate,
    "search-results",
    params.search,
    params.limit,
    params.offset,
    params.caseSensitive,
  ],
} as const;
