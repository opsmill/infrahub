import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetTreeNodesByParentParams,
  getTreeNodesByParent,
} from "@/entities/nodes/hierarchy/domain/get-tree-nodes-by-parent";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

/** Page size for tree node queries - larger than default to reduce requests for hierarchical data */
export const TREE_NODES_PAGE_SIZE = 80;

export type GetTreeNodesByParentQueryOptionsParams = Omit<
  GetTreeNodesByParentParams,
  keyof PaginationParams
>;

export function getTreeNodesByParentInfiniteQueryOptions(
  params: GetTreeNodesByParentQueryOptionsParams
) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.tree(params),
    queryFn: async ({ pageParam }) => {
      return getTreeNodesByParent({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < TREE_NODES_PAGE_SIZE) {
        return;
      }
      return lastPageParam + TREE_NODES_PAGE_SIZE;
    },
  });
}

export type UseGetTreeNodesByParentConfig = InfiniteQueryConfig<
  typeof getTreeNodesByParentInfiniteQueryOptions
>;

export function useGetTreeNodesByParent(
  params: Omit<GetTreeNodesByParentQueryOptionsParams, keyof ContextParams>,
  config?: UseGetTreeNodesByParentConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery({
    ...getTreeNodesByParentInfiniteQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
