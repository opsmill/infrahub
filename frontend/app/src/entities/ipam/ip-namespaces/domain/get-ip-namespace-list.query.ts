import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import {
  type GetIpNamespaceListParams,
  getIpNamespaceList,
} from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

export type GetIpNamespaceListInfiniteQueryOptionsParams = Omit<
  GetIpNamespaceListParams,
  keyof PaginationParams
>;

export function getIpNamespaceListInfiniteQueryOptions(
  params: GetIpNamespaceListInfiniteQueryOptionsParams
) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: IP_NAMESPACE_GENERIC }),
    queryFn: async ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getIpNamespaceList({
        ...params,
        offset: pageParam.offset,
        limit: pageParam.limit,
      });
    },
    initialPageParam: { offset: 0, limit: DEFAULT_PAGE_SIZE },
    getNextPageParam: (lastPage, allPages, lastPageParam) => {
      if (lastPage.items.length < lastPageParam.limit) {
        return;
      }

      const totalCount = allPages[0]?.count ?? 0;
      const pageSize = totalCount > 0 ? calculateDynamicPageSize(totalCount) : DEFAULT_PAGE_SIZE;

      return {
        offset: lastPageParam.offset + lastPageParam.limit,
        limit: pageSize,
      };
    },
  });
}

export function useGetIpNamespaceList(
  params?: Omit<GetIpNamespaceListInfiniteQueryOptionsParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getIpNamespaceListInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
