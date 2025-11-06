import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import {
  type GetResourcePoolUtilizationParams,
  getResourceUtilization,
} from "@/entities/resource-manager/domain/get-resource-utilization";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/domain/resource-manager.query-keys";

export function getResourceUtilizationQueryOptions(params: GetResourcePoolUtilizationParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.utilization(params),
    queryFn: () => getResourceUtilization(params),
  });
}

export function useGetResourceUtilization(
  { resourceId }: Omit<GetResourcePoolUtilizationParams, keyof ContextParams>,
  config?: QueryConfig<typeof getResourceUtilizationQueryOptions>
) {
  return useQuery({
    ...getResourceUtilizationQueryOptions({ resourceId }),
    ...config,
  });
}
