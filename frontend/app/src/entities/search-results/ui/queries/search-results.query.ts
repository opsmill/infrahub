import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OffsetPagination,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { SearchResultsFromApiParams } from "@/entities/search-results/api/search-results";
import { getSearchResults } from "@/entities/search-results/domain/get-search-results";
import type { SearchResultItem } from "@/entities/search-results/types";
import { searchResultsQueryKeys } from "@/entities/search-results/ui/queries/search-results.query-keys";

type SearchResultsInfiniteParams = Omit<SearchResultsFromApiParams, "limit" | "offset"> & {
  totalCount?: number;
};

function searchResultsInfiniteQueryOptions(
  params: SearchResultsInfiniteParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize<SearchResultItem[]>(
    {
      queryKey: searchResultsQueryKeys.all(params),
      queryFn: async ({ pageParam }: { pageParam: OffsetPagination }) => {
        const result = await getSearchResults({
          ...params,
          limit: pageParam.limit,
          offset: pageParam.offset,
        });
        return result.results;
      },
    },
    config
  );
}

export function useSearchResults(
  params: Omit<SearchResultsFromApiParams, keyof ContextParams | "limit" | "offset"> & {
    totalCount?: number;
  },
  config?: { enabled?: boolean }
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery({
    ...searchResultsInfiniteQueryOptions(
      {
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        ...params,
      },
      { totalCount: params.totalCount }
    ),
    ...config,
  });
}
