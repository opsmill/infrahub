import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNumberPoolParams,
  getNumberPool,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getNumberPoolQueryOptions(params: GetNumberPoolParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPool(params),
    queryFn: () => getNumberPool(params),
  });
}

export function useGetNumberPool(poolId: string) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNumberPoolQueryOptions({
      poolId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
