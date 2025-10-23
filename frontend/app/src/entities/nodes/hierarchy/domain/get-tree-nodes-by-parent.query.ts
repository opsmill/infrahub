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

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

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
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
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
