import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import {
  type GetIpNamespaceListParams,
  getIpNamespaceList,
} from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
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
    queryFn: async ({ pageParam }) => {
      return getIpNamespaceList({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
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
