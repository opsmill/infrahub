import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { PaginationParams } from "@/shared/api/types";

import {
  OBJECTS_PER_PAGE,
  type ProposedChangesFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-changes-from-api";
import { getProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/domain/proposed-changes.query-keys";

type GetProposedChangesInfiniteQueryOptionsParams = Omit<
  ProposedChangesFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangesInfiniteQueryOptions(
  params: GetProposedChangesInfiniteQueryOptionsParams
) {
  return infiniteQueryOptions({
    queryKey: proposedChangesQueryKeys.list(params),
    queryFn: ({ pageParam }) => {
      return getProposedChanges({
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

export function useGetProposedChanges(params: GetProposedChangesInfiniteQueryOptionsParams) {
  return useInfiniteQuery(getProposedChangesInfiniteQueryOptions(params));
}
