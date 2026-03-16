import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectRelationshipsParams,
  getObjectRelationships,
} from "@/entities/nodes/relationships/domain/get-object-relationships/get-object-relationships";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import { relationshipsQueryKeys } from "@/entities/nodes/relationships/domain/relationships.query-keys";

export type GetObjectRelationshipsQueryOptionsParams = Omit<
  GetObjectRelationshipsParams,
  keyof PaginationParams
>;

export function getObjectRelationshipsQueryOptions(
  params: GetObjectRelationshipsQueryOptionsParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize(
    {
      queryKey: relationshipsQueryKeys.list({
        ...params,
        objectKind: params.parentKind,
        objectId: params.parentId,
      }),
      queryFn: ({ pageParam }) =>
        getObjectRelationships({
          ...params,
          offset: pageParam.offset,
          limit: pageParam.limit,
        }),
    },
    config
  );
}

export type UseObjectRelationshipsParams = Omit<
  GetObjectRelationshipsQueryOptionsParams,
  keyof ContextParams
>;

export function useObjectRelationships(
  params: UseObjectRelationshipsParams,
  config?: InfiniteQueryConfig<typeof getObjectRelationshipsQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const {
    data: totalCount,
    isSuccess: isCountSuccess,
    isError: isCountError,
  } = useGetRelationshipCount({
    objectKind: params.parentKind,
    objectId: params.parentId,
    relationshipName: params.relationshipName,
  });

  return useInfiniteQuery({
    ...getObjectRelationshipsQueryOptions(
      {
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      },
      { totalCount }
    ),
    ...config,
    enabled: (isCountSuccess || isCountError) && config?.enabled,
  });
}
