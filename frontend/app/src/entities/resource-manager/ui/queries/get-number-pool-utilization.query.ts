import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NumberPoolDivisionSelector } from "@/entities/resource-manager/domain/model/number-pool";
import {
  type GetNumberPoolUtilizationParams,
  getNumberPoolUtilization,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool-utilization";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getNumberPoolUtilizationQueryOptions(params: GetNumberPoolUtilizationParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPoolUtilization(params),
    queryFn: () => getNumberPoolUtilization(params),
  });
}

export interface UseGetNumberPoolUtilizationParams {
  poolId: string;
  division?: NumberPoolDivisionSelector;
}

export function useGetNumberPoolUtilization({
  poolId,
  division,
}: UseGetNumberPoolUtilizationParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNumberPoolUtilizationQueryOptions({
      poolId,
      division,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
