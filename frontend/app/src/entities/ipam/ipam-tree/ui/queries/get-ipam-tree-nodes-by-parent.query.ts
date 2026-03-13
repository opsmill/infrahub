import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import {
  type GetIpamTreeNodesByParentParams,
  getIpamTreeNodesByParent,
} from "@/entities/ipam/ipam-tree/domain/get-ipam-tree-nodes-by-parent";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const IPAM_NODES_PER_PAGE = 80;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetIpamTreeNodesByParentQueryOptionsParams = Omit<
  GetIpamTreeNodesByParentParams,
  keyof PaginationParams | keyof ContextParams
>;

export function getIpamTreeNodesByParentInfiniteQueryOptions(
  params: GetIpamTreeNodesByParentQueryOptionsParams & ContextParams
) {
  return infiniteQueryOptions({
    queryKey: [
      ...objectQueryKeys.tree({ objectKind: IP_PREFIX_GENERIC, ...params }),
      params.namespaceId,
      params.search,
    ],
    queryFn: async ({ pageParam }) => {
      return getIpamTreeNodesByParent({
        ...params,
        limit: IPAM_NODES_PER_PAGE,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < IPAM_NODES_PER_PAGE) {
        return;
      }
      return lastPageParam + IPAM_NODES_PER_PAGE;
    },
  });
}

export type UseGetIpamTreeNodesByParentConfig = InfiniteQueryConfig<
  typeof getIpamTreeNodesByParentInfiniteQueryOptions
>;

export function useGetIpamTreeNodesByParent(
  params: GetIpamTreeNodesByParentQueryOptionsParams,
  config?: UseGetIpamTreeNodesByParentConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery({
    ...getIpamTreeNodesByParentInfiniteQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
