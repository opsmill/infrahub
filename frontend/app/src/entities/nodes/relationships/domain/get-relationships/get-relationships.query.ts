import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRelationshipsParams,
  getRelationships,
  RELATIONSHIPS_PER_PAGE,
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
    queryFn: ({ pageParam }) => {
      return getRelationships({ peer, offset: pageParam, search, filterQuery, branchName, atDate });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < RELATIONSHIPS_PER_PAGE) {
        return;
      }
      return lastPageParam + RELATIONSHIPS_PER_PAGE;
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
