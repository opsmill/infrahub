import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetCountsParams, getCounts } from "@/entities/role-manager/domain/get-counts";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getCountsQueryOptions(params: GetCountsParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.counts(params),
    queryFn: () => getCounts(params),
  });
}

export function useGetCounts() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getCountsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
