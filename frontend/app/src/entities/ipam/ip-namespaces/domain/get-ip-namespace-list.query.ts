import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import {
  type GetIpNamespaceListParams,
  getIpNamespaceList,
} from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

export type GetIpNamespaceListInfiniteQueryOptionsParams = Omit<
  GetIpNamespaceListParams,
  keyof PaginationParams
>;

export function getIpNamespaceListInfiniteQueryOptions(
  params: GetIpNamespaceListInfiniteQueryOptionsParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize(
    {
      queryKey: objectQueryKeys.list({ ...params, objectKind: IP_NAMESPACE_GENERIC }),
      queryFn: ({ pageParam }) =>
        getIpNamespaceList({
          ...params,
          offset: pageParam.offset,
          limit: pageParam.limit,
        }),
    },
    config
  );
}

export function useGetIpNamespaceList(
  params?: Omit<GetIpNamespaceListInfiniteQueryOptionsParams, keyof ContextParams>,
  config?: InfiniteQueryConfig<typeof getIpNamespaceListInfiniteQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const {
    data: totalCount,
    isSuccess: isCountSuccess,
    isError: isCountError,
  } = useObjectsCount({
    objectKind: IP_NAMESPACE_GENERIC,
    filters: params?.filters,
  });

  return useInfiniteQuery({
    ...getIpNamespaceListInfiniteQueryOptions(
      {
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      },
      { totalCount }
    ),
    ...config,
    enabled: (isCountSuccess || isCountError) && config?.enabled,
  });
}
