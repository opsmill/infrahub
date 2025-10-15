import { queryOptions, useQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";

import { type SearchDocsParams, searchDocs } from "@/entities/search-anywhere/domain/search-docs";

type searchDocsQueryOptionsParams = SearchDocsParams;

export function searchDocsQueryOptions({ query, limit = 3 }: searchDocsQueryOptionsParams) {
  return queryOptions({
    queryKey: ["search-docs", query, limit],
    queryFn: () => searchDocs({ query, limit }),
  });
}

export function useGetSearchDocs(
  params: searchDocsQueryOptionsParams,
  config?: InfiniteQueryConfig<typeof searchDocsQueryOptions>
) {
  return useQuery({ ...searchDocsQueryOptions(params), ...config });
}
