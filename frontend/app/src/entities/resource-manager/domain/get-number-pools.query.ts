import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
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
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNumberPoolsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      objectKinds,
    })
  );
}
