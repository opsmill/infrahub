import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getWeightedPrefixKinds } from "@/entities/resource-manager/domain/rules/get-weighted-prefix-kinds";
import {
  type GetIpPoolUtilizationParams,
  getIpPoolUtilization,
} from "@/entities/resource-manager/domain/use-cases/get-ip-pool-utilization";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

export function getIpPoolUtilizationQueryOptions(params: GetIpPoolUtilizationParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.ipPoolUtilization(params),
    queryFn: () => getIpPoolUtilization(params),
  });
}

export function useGetIpPoolUtilization(
  poolId: string,
  config?: QueryConfig<typeof getIpPoolUtilizationQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const nodeSchemas = useAtomValue(nodeSchemasAtom);

  return useQuery({
    ...getIpPoolUtilizationQueryOptions({
      poolId,
      weightedKinds: getWeightedPrefixKinds(nodeSchemas),
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
