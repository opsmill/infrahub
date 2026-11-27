import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetResourceAllocatedParams,
  getResourceAllocated,
} from "@/entities/resource-manager/domain/use-cases/get-resource-allocated";
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
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getResourceAllocatedQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
