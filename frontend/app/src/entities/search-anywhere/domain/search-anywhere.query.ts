import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type SearchAnywhereParams,
  searchAnywhere,
} from "@/entities/search-anywhere/domain/search-anywhere";

export function searchAnywhereQueryOptions({ branchName, search, atDate }: SearchAnywhereParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "search-objects", search],
    queryFn: async () => searchAnywhere({ branchName, search, atDate }),
  });
}

export function useGetSearchAnywhere(
  params: Omit<SearchAnywhereParams, keyof ContextParams>,
  config?: QueryConfig<typeof searchAnywhereQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...searchAnywhereQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
