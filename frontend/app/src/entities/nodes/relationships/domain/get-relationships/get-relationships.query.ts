import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRelationshipsParams,
  getRelationships,
} from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";

export type GetRelationshipsQueryParams = Omit<GetRelationshipsParams, keyof PaginationParams>;

export function getRelationshipsInfiniteQueryOptions({
  peer,
  search,
  branchName,
  atDate,
  filterQuery,
}: GetRelationshipsQueryParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, atDate, "relationships", peer, search, filterQuery],
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getRelationships({
        peer,
        offset: pageParam.offset,
        limit: pageParam.limit,
        search,
        filterQuery,
        branchName,
        atDate,
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

export function useRelationships(params: Omit<GetRelationshipsParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getRelationshipsInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
