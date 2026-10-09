import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNumberPoolAllocationsParams,
  getNumberPoolAllocations,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool-allocations";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export const NUMBER_POOL_ALLOCATIONS_PAGE_SIZE = 100;

export type GetNumberPoolAllocationsQueryParams = Omit<
  GetNumberPoolAllocationsParams,
  "offset" | "limit"
>;

export function getNumberPoolAllocationsInfiniteQueryOptions(
  params: GetNumberPoolAllocationsQueryParams
) {
  return infiniteQueryOptions({
    queryKey: resourceManagerQueryKeys.numberPoolAllocations(params),
    queryFn: ({ pageParam }) =>
      getNumberPoolAllocations({
        ...params,
        offset: pageParam,
        limit: NUMBER_POOL_ALLOCATIONS_PAGE_SIZE,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < NUMBER_POOL_ALLOCATIONS_PAGE_SIZE) {
        return;
      }
      return lastPageParam + NUMBER_POOL_ALLOCATIONS_PAGE_SIZE;
    },
  });
}

export interface UseGetNumberPoolAllocationsParams {
  poolId: string;
  rangeId?: string;
}

export function useGetNumberPoolAllocations({
  poolId,
  rangeId,
}: UseGetNumberPoolAllocationsParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getNumberPoolAllocationsInfiniteQueryOptions({
      poolId,
      rangeId,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
