import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetPoolUtilizationParams,
  getPoolUtilization,
} from "@/entities/resource-manager/domain/use-cases/get-pool-utilization";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getPoolUtilizationQueryOptions(params: GetPoolUtilizationParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.utilization(params),
    queryFn: () => getPoolUtilization(params),
  });
}

export function useGetPoolUtilization(
  params: Omit<GetPoolUtilizationParams, keyof ContextParams>,
  config?: QueryConfig<typeof getPoolUtilizationQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getPoolUtilizationQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
