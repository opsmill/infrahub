import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import { type SearchDocsParams, searchDocs } from "@/entities/navigation/domain/search-docs";
import { searchAnywhereQueryKeys } from "@/entities/navigation/ui/queries/search-anywhere.query-keys";

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
