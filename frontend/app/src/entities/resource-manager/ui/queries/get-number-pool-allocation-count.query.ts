import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNumberPoolAllocationCountParams,
  getNumberPoolAllocationCount,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool-allocation-count";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getNumberPoolAllocationCountQueryOptions(
  params: GetNumberPoolAllocationCountParams
) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPoolAllocationCount(params),
    queryFn: () => getNumberPoolAllocationCount(params),
  });
}

export interface UseGetNumberPoolAllocationCountParams {
  poolId: string;
  rangeId?: string;
}

export function useGetNumberPoolAllocationCount({
  poolId,
  rangeId,
}: UseGetNumberPoolAllocationCountParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNumberPoolAllocationCountQueryOptions({
      poolId,
      rangeId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
