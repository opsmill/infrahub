import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  type GetRelationshipsParams,
  getRelationships,
} from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";

export type GetRelationshipsQueryParams = Omit<GetRelationshipsParams, keyof PaginationParams>;

export function getRelationshipsInfiniteQueryOptions(
  { peer, search, branchName, atDate, filterQuery }: GetRelationshipsQueryParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize(
    {
      queryKey: [branchName, atDate, "relationships", peer, search, filterQuery],
      queryFn: ({ pageParam }) => {
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
    },
    config
  );
}

export function useRelationships(
  params: Omit<GetRelationshipsParams, keyof ContextParams>,
  config?: InfiniteQueryConfig<typeof getRelationshipsInfiniteQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const {
    data: totalCount,
    isSuccess: isCountSuccess,
    isError: isCountError,
  } = useObjectsCount({
    objectKind: params.peer,
    filters: params.search ? [{ name: "any__value", value: params.search }] : undefined,
  });

  return useInfiniteQuery({
    ...getRelationshipsInfiniteQueryOptions(
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
