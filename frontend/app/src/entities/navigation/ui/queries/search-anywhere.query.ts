import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { searchAnywhere } from "@/entities/navigation/domain/use-cases/search-anywhere";
import {
  type SearchObjectsKeyParams,
  searchAnywhereQueryKeys,
} from "@/entities/navigation/ui/queries/search-anywhere.query-keys";

export const SEARCH_BATCH_SIZE = 20;

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
