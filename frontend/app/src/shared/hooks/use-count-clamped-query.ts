import { type QueryKey, type UseQueryOptions, useQuery } from "@tanstack/react-query";

import { clampPage, getOffset, getTotalPages } from "@/shared/utils/table-pagination";

interface CountClampedQueryParams {
  page: number;
  pageSize: number;
}

/**
 * Asks for the requested page and, when the server's count puts it past the end, for the last real
 * page instead. Only the server's count can say which page is the last one, so the clamp follows
 * the first answer; the url is left alone and the next page change overwrites it.
 */
export function useCountClampedQuery<TData extends { count: number }, TKey extends QueryKey>(
  { page, pageSize }: CountClampedQueryParams,
  getQueryOptions: (offset: number) => UseQueryOptions<TData, Error, TData, TKey>
) {
  const requested = useQuery(getQueryOptions(getOffset(page, pageSize)));
  // A placeholder count belongs to the row set before this one, so it cannot judge this page.
  const count = requested.isPlaceholderData ? undefined : requested.data?.count;
  const currentPage = count === undefined ? page : clampPage(page, getTotalPages(count, pageSize));
  const isClamped = currentPage !== page;
  const clamped = useQuery({
    ...getQueryOptions(getOffset(currentPage, pageSize)),
    enabled: isClamped,
  });

  return { page: currentPage, query: isClamped ? clamped : requested };
}
