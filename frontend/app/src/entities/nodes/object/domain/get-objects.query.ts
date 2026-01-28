import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetObjectsParams, getObjects } from "@/entities/nodes/object/domain/get-objects";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetObjectsQueryParams = Omit<GetObjectsParams, keyof PaginationParams>;

export function getObjectsInfiniteQueryOptions(params: GetObjectsQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getObjects({
        ...params,
        offset: pageParam.offset,
        limit: pageParam.limit,
      });
    },
    initialPageParam: { offset: 0, limit: DEFAULT_PAGE_SIZE },
    getNextPageParam: (lastPage, allPages, lastPageParam) => {
      // If we got fewer items than requested, there are no more pages
      if (lastPage.items.length < lastPageParam.limit) {
        return;
      }

      // Get count from the first page and calculate dynamic page size (locked after first page)
      const totalCount = allPages[0]?.count ?? 0;
      const pageSize = totalCount > 0 ? calculateDynamicPageSize(totalCount) : DEFAULT_PAGE_SIZE;

      return {
        offset: lastPageParam.offset + lastPageParam.limit,
        limit: pageSize,
      };
    },
  });
}

export function useObjects(params: Omit<GetObjectsQueryParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getObjectsInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
