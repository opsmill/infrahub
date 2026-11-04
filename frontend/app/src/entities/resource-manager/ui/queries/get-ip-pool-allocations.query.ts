import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetIpPoolAllocationsParams,
  getIpPoolAllocations,
} from "@/entities/resource-manager/domain/use-cases/get-ip-pool-allocations";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export const IP_POOL_ALLOCATIONS_PAGE_SIZE = 100;

export type GetIpPoolAllocationsQueryParams = Omit<GetIpPoolAllocationsParams, "offset" | "limit">;

export function getIpPoolAllocationsInfiniteQueryOptions(params: GetIpPoolAllocationsQueryParams) {
  return infiniteQueryOptions({
    queryKey: resourceManagerQueryKeys.ipPoolAllocations(params),
    queryFn: ({ pageParam }) =>
      getIpPoolAllocations({ ...params, offset: pageParam, limit: IP_POOL_ALLOCATIONS_PAGE_SIZE }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.allocations.length < IP_POOL_ALLOCATIONS_PAGE_SIZE) {
        return;
      }
      return lastPageParam + IP_POOL_ALLOCATIONS_PAGE_SIZE;
    },
  });
}

export interface UseGetIpPoolAllocationsParams {
  poolId: string;
  resourceId: string;
}

export function useGetIpPoolAllocations({ poolId, resourceId }: UseGetIpPoolAllocationsParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getIpPoolAllocationsInfiniteQueryOptions({
      poolId,
      resourceId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
