import {
  infiniteQueryOptions,
  queryOptions,
  useInfiniteQuery,
  useQuery,
} from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { keepPreviousDataWithin } from "@/shared/api/keep-previous-data-within";
import type { ContextParams, InfiniteQueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { getOffset } from "@/shared/utils/table-pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type SearchAnywhereResult,
  searchAnywhere,
} from "@/entities/navigation/domain/use-cases/search-anywhere";
import {
  type SearchObjectsKeyParams,
  type SearchResultsPageKeyParams,
  searchAnywhereQueryKeys,
} from "@/entities/navigation/ui/queries/search-anywhere.query-keys";

export const SEARCH_BATCH_SIZE = 20;

export const SEARCH_RESULTS_PAGE_SIZE = 20;

export function searchAnywhereQueryOptions(params: SearchObjectsKeyParams) {
  return infiniteQueryOptions({
    queryKey: searchAnywhereQueryKeys.objects(params),
    queryFn: ({ pageParam }) => searchAnywhere({ ...params, limit: pageParam }),
    initialPageParam: SEARCH_BATCH_SIZE,
    getNextPageParam: (lastPage, _, lastLimit) =>
      lastPage.hasMore ? lastLimit + SEARCH_BATCH_SIZE : undefined,
    maxPages: 1, // Each page already holds every row loaded so far.
    select: (data) => data.pages[0],
    refetchOnWindowFocus: false,
    gcTime: 0, // A repeated search starts again from the first batch instead of every row loaded before.
  });
}

export function useGetSearchAnywhere(
  params: Omit<SearchObjectsKeyParams, keyof ContextParams>,
  config?: InfiniteQueryConfig<typeof searchAnywhereQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery({
    ...searchAnywhereQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}

export function searchResultsPageQueryOptions({
  limit,
  offset,
  ...listParams
}: SearchResultsPageKeyParams) {
  return queryOptions({
    queryKey: searchAnywhereQueryKeys.resultsPage({ ...listParams, limit, offset }),
    queryFn: () => searchAnywhere({ ...listParams, limit, offset }),
    placeholderData: keepPreviousDataWithin(
      searchAnywhereQueryKeys.results(listParams),
      (page: SearchAnywhereResult) => page.matchingObjects.length > 0
    ),
    refetchOnWindowFocus: false, // The user comes back to this tab after opening each result in a new one.
  });
}

interface UseGetSearchResultsPageParams {
  search: string;
  caseSensitive: boolean;
  page: number;
}

export function useGetSearchResultsPage({
  search,
  caseSensitive,
  page,
}: UseGetSearchResultsPageParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...searchResultsPageQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      search,
      caseSensitive,
      limit: SEARCH_RESULTS_PAGE_SIZE,
      offset: getOffset(page, SEARCH_RESULTS_PAGE_SIZE),
    }),
    enabled: search !== "",
  });
}
