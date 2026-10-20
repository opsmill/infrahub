import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNumberPoolDivisionsParams,
  getNumberPoolDivisions,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool-divisions";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getNumberPoolDivisionsQueryOptions(params: GetNumberPoolDivisionsParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPoolDivisions(params),
    queryFn: () => getNumberPoolDivisions(params),
  });
}

export function useGetNumberPoolDivisions(poolId: string) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getNumberPoolDivisionsQueryOptions({
      poolId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
