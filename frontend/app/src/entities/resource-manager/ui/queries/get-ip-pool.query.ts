import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetIpPoolParams,
  getIpPool,
} from "@/entities/resource-manager/domain/use-cases/get-ip-pool";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getIpPoolQueryOptions(params: GetIpPoolParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.ipPool(params),
    queryFn: () => getIpPool(params),
  });
}

export function useGetIpPool(poolId: string) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getIpPoolQueryOptions({ poolId, branchName: currentBranch.name, atDate: timeMachineDate })
  );
}
