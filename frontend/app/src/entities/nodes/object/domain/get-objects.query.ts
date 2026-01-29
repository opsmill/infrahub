import { useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";
import {
  infiniteQueryOptionsWithOptimizedPageSize,
  type OptimizedPageSizeConfig,
} from "@/shared/libs/react-query/infinite-query-options-with-optimized-page-size";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetObjectsParams, getObjects } from "@/entities/nodes/object/domain/get-objects";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetObjectsQueryParams = Omit<GetObjectsParams, keyof PaginationParams>;

export function getObjectsInfiniteQueryOptions(
  params: GetObjectsQueryParams,
  config?: OptimizedPageSizeConfig
) {
  return infiniteQueryOptionsWithOptimizedPageSize(
    {
      queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
      queryFn: ({ pageParam }) =>
        getObjects({
          ...params,
          offset: pageParam.offset,
          limit: pageParam.limit,
        }),
    },
    config
  );
}

export function useObjects(
  params: Omit<GetObjectsQueryParams, keyof ContextParams>,
  config?: InfiniteQueryConfig<typeof getObjectsInfiniteQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  const { data: totalCount } = useObjectsCount({
    objectKind: params.schema.kind!,
    filters: params.filters,
  });

  return useInfiniteQuery({
    ...getObjectsInfiniteQueryOptions(
      {
        ...params,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      },
      { totalCount }
    ),
    ...config,
    enabled: totalCount !== undefined && config?.enabled,
  });
}
