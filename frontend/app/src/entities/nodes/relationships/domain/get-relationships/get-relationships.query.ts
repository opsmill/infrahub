import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import {
  GetRelationshipsParams,
  RELATIONSHIPS_PER_PAGE,
  getRelationships,
} from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export type GetRelationshipsQueryParams = Omit<GetRelationshipsParams, keyof PaginationParams>;

export function getRelationshipsInfiniteQueryOptions({
  peer,
  search,
  parentId,
  branchName,
  atDate,
}: GetRelationshipsQueryParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, atDate, "relationships", peer, search, parentId],
    queryFn: ({ pageParam }) => {
      return getRelationships({ peer, offset: pageParam, search, parentId, branchName, atDate });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < RELATIONSHIPS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + RELATIONSHIPS_PER_PAGE;
    },
  });
}

export function useRelationships(params: Omit<GetRelationshipsParams, keyof ContextParams>) {
  const currentBranch = useAtomValue(currentBranchAtom);
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getRelationshipsInfiniteQueryOptions({
      ...params,
      branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME,
      atDate: timeMachineDate,
    })
  );
}
