import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetPoolUtilizationParams,
  getPoolUtilization,
} from "@/entities/resource-manager/domain/get-pool-utilization";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/domain/resource-manager.query-keys";

export function getPoolUtilizationQueryOptions(params: GetPoolUtilizationParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.utilization(params),
    queryFn: () => getPoolUtilization(params),
  });
}

export function useGetPoolUtilization(
  params: GetPoolUtilizationParams,
  config?: QueryConfig<typeof getPoolUtilizationQueryOptions>
) {
  return useQuery({
    ...getPoolUtilizationQueryOptions(params),
    ...config,
  });
}
