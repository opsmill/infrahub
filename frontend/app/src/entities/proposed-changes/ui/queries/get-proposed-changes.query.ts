import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { PaginationParams } from "@/shared/api/types";
import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { ProposedChangesFromApiParams } from "@/entities/proposed-changes/api/get-proposed-changes-from-api";
import { getProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";

type GetProposedChangesInfiniteQueryOptionsParams = Omit<
  ProposedChangesFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangesInfiniteQueryOptions(
  params: GetProposedChangesInfiniteQueryOptionsParams
) {
  return infiniteQueryOptions({
    queryKey: proposedChangesQueryKeys.list(params),
    queryFn: ({ pageParam }: { pageParam: { offset: number; limit: number } }) => {
      return getProposedChanges({
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

export function useGetProposedChanges(params: GetProposedChangesInfiniteQueryOptionsParams) {
  return useInfiniteQuery(getProposedChangesInfiniteQueryOptions(params));
}
