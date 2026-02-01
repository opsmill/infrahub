import { infiniteQueryOptions, type QueryKey } from "@tanstack/react-query";

import { calculateDynamicPageSize, DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

export interface OffsetPagination {
  offset: number;
  limit: number;
}

export interface OptimizedPageSizeConfig {
  totalCount?: number;
}

/**
 * Extends infiniteQueryOptions with dynamic page size based on total count.
 * Expects queryFn to return an array.
 *
 * @param options - Standard infiniteQueryOptions input (queryKey, queryFn, etc.)
 * @param config
 * @param config.totalCount - Total items available (from separate count query)
 *
 * @example
 * infiniteQueryOptionsWithOptimizedPageSize(
 *   {
 *     queryKey: ['objects', kind],
 *     queryFn: ({ pageParam }) => fetchObjects(pageParam),
 *   },
 *   { totalCount: 5000 }
 * )
 */
export function infiniteQueryOptionsWithOptimizedPageSize<
  TQueryFnData extends unknown[],
  TQueryKey extends QueryKey = QueryKey,
>(
  options: {
    queryKey: TQueryKey;
    queryFn: (context: { pageParam: OffsetPagination }) => Promise<TQueryFnData>;
    staleTime?: number;
    gcTime?: number;
  },
  config: OptimizedPageSizeConfig = {}
) {
  const { totalCount } = config;

  const pageSize =
    totalCount && totalCount > 0 ? calculateDynamicPageSize(totalCount) : DEFAULT_PAGE_SIZE;

  return infiniteQueryOptions({
    ...options,
    initialPageParam: { offset: 0, limit: pageSize },
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < lastPageParam.limit) {
        return undefined;
      }
      return {
        offset: lastPageParam.offset + lastPageParam.limit,
        limit: pageSize,
      };
    },
  });
}
