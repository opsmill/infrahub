import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { searchAnywhereQueryKeys } from "@/entities/navigation/domain/search-anywhere.query-keys";
import { type SearchDocsParams, searchDocs } from "@/entities/navigation/domain/search-docs";

export function searchDocsQueryOptions({ query, limit = 3 }: SearchDocsParams) {
  return queryOptions({
    queryKey: searchAnywhereQueryKeys.docs({ query, limit }),
    queryFn: () => searchDocs({ query, limit }),
    enabled: !!query, // prevent sending query with empty string
  });
}

export function useGetSearchDocs(
  params: SearchDocsParams,
  config?: QueryConfig<typeof searchDocsQueryOptions>
) {
  return useQuery({ ...searchDocsQueryOptions(params), ...config });
}
