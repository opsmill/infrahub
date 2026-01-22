import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectRelationshipsParams,
  getObjectRelationships,
} from "@/entities/nodes/relationships/domain/get-object-relationships/get-object-relationships";
import { relationshipsQueryKeys } from "@/entities/nodes/relationships/domain/relationships.query-keys";

export type GetObjectRelationshipsQueryOptionsParams = Omit<
  GetObjectRelationshipsParams,
  keyof PaginationParams
>;

export function getObjectRelationshipsQueryOptions(params: GetObjectRelationshipsParams) {
  return infiniteQueryOptions({
    queryKey: relationshipsQueryKeys.list({
      ...params,
      objectKind: params.parentKind,
      objectId: params.parentId,
    }),
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getObjectRelationships({
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

export type UseObjectRelationshipsParams = Omit<
  GetObjectRelationshipsQueryOptionsParams,
  keyof ContextParams
>;

export function useObjectRelationships(params: UseObjectRelationshipsParams) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getObjectRelationshipsQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
