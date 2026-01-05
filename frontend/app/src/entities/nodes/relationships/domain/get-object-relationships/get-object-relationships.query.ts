import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectRelationshipsParams,
  getObjectRelationships,
  OBJECT_RELATIONSHIPS_PER_PAGE,
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
    queryFn: ({ pageParam }) => {
      return getObjectRelationships({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECT_RELATIONSHIPS_PER_PAGE) {
        return;
      }
      return lastPageParam + OBJECT_RELATIONSHIPS_PER_PAGE;
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
