import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import { RESOURCE_POOL_UTILIZATION_KIND } from "@/entities/resource-manager/constants";

import {
  type GetResourcePoolUtilizationParams,
  getResourceUtilization,
} from "./get-resource-utilization";

export function getResourceUtilizationQueryOptions(params: GetResourcePoolUtilizationParams) {
  return queryOptions({
    queryKey: [RESOURCE_POOL_UTILIZATION_KIND, params.resourceId],
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
