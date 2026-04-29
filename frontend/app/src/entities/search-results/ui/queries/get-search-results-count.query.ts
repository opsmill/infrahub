import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { searchResultsFromApi } from "@/entities/search-results/api/search-results";
import { searchResultsQueryKeys } from "@/entities/search-results/ui/queries/search-results.query-keys";

type SearchResultsCountParams = ContextParams & {
  search: string;
  caseSensitive?: boolean;
};

function searchResultsCountQueryOptions(params: SearchResultsCountParams) {
  return queryOptions({
    queryKey: [...searchResultsQueryKeys.all(params), "count"],
    queryFn: async () => {
      const { data, errors } = await searchResultsFromApi({
        ...params,
        limit: 1,
        offset: 0,
      });

      if (errors) {
        throw new Error(errors.map((e) => e.message).join("; "));
      }

      return data?.InfrahubSearchAnywhere?.count ?? 0;
    },
  });
}

export function useSearchResultsCount(
  params: Omit<SearchResultsCountParams, keyof ContextParams>,
  config?: { enabled?: boolean }
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...searchResultsCountQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
