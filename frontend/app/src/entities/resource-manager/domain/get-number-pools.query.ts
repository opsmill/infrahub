import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  type GetNumberPoolsParams,
  getNumberPools,
} from "@/entities/resource-manager/domain/get-number-pools";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/domain/resource-manager.query-keys";

export function getNumberPoolsQueryOptions(params: GetNumberPoolsParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPools(params),
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
