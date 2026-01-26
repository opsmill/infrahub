import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetIpPrefixListParams,
  getIpPrefixList,
} from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-list";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetIpPrefixListInfiniteQueryParams = Omit<GetIpPrefixListParams, keyof PaginationParams>;

export function getIpPrefixListInfiniteQueryOptions(params: GetIpPrefixListInfiniteQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getIpPrefixList({
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

export function useGetIpPrefixList(
  params: Omit<GetIpPrefixListInfiniteQueryParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getIpPrefixListInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
