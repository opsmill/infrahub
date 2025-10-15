import { queryOptions, useQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";

import { searchAnywhereQueryKeys } from "@/entities/search-anywhere/domain/search-anywhere.query-keys";
import { type SearchDocsParams, searchDocs } from "@/entities/search-anywhere/domain/search-docs";

export function searchDocsQueryOptions({ query, limit = 3 }: SearchDocsParams) {
  return queryOptions({
    queryKey: searchAnywhereQueryKeys.docs({ query, limit }),
    queryFn: () => searchDocs({ query, limit }),
  });
}

export function useGetSearchDocs(
  params: SearchDocsParams,
  config?: InfiniteQueryConfig<typeof searchDocsQueryOptions>
) {
  return useQuery({ ...searchDocsQueryOptions(params), ...config });
}
