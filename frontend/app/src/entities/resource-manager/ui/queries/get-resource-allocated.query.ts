import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import {
  type GetResourceAllocatedParams,
  getResourceAllocated,
} from "@/entities/resource-manager/domain/get-resource-allocated";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getResourceAllocatedQueryOptions(params: GetResourceAllocatedParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.allocated(params),
    queryFn: () => getResourceAllocated(params),
  });
}

export function useGetResourceAllocated(
  params: Omit<GetResourceAllocatedParams, keyof ContextParams>,
  config?: QueryConfig<typeof getResourceAllocatedQueryOptions>
) {
  return useQuery({
    ...getResourceAllocatedQueryOptions(params),
    ...config,
  });
}
