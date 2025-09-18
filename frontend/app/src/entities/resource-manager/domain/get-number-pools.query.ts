import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams } from "@/shared/api/types";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/constants";

import { type GetNumberPoolsParams, getNumberPools } from "./get-number-pools";

export function getNumberPoolsQueryOptions(params: GetNumberPoolsParams) {
  return queryOptions({
    queryKey: [params.branchName, params.atDate, NUMBER_POOL_KIND, params.objectKinds],
    queryFn: () => getNumberPools(params),
  });
}

export function useGetNumberPools({
  objectKinds,
}: Omit<GetNumberPoolsParams, keyof ContextParams>) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return useQuery(
    getNumberPoolsQueryOptions({
      branchName: currentBranchName,
      atDate: timeMachineDate,
      objectKinds,
    })
  );
}
