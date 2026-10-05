import { type QueryKey, type UseQueryOptions, useQuery } from "@tanstack/react-query";

import { clampPage, getOffset, getTotalPages } from "@/shared/utils/table-pagination";

const isPastEnd = (page: number, pageSize: number, count: number | undefined) =>
  count !== undefined && clampPage(page, getTotalPages(count, pageSize)) !== page;

interface CountClampedQueryParams {
  page: number;
  pageSize: number;
}

/**
 * Asks for the requested page and, when the server's count puts it past the end, for the last real
 * page instead. Only the server's count can say which page is the last one, so the clamp follows
 * the first answer; the url is left alone and the next page change overwrites it. Once the
 * requested page is known to be past the end, it stops being fetched, until a newer count from the
 * clamped page shows that the row set has grown to include it.
 */
export function useCountClampedQuery<TData extends { count: number }, TKey extends QueryKey>(
  { page, pageSize }: CountClampedQueryParams,
  getQueryOptions: (offset: number) => UseQueryOptions<TData, Error, TData, TKey>
) {
  const requestedOptions = getQueryOptions(getOffset(page, pageSize));
  const { enabled = true } = requestedOptions;
  // Reads the requested page's cached answer without fetching, so the clamp is known before the
  // requested page is fetched.
  const cached = useQuery({ ...requestedOptions, enabled: false });
  // A placeholder count belongs to the row set before this one, so it cannot judge this page.
  const count = cached.isPlaceholderData ? undefined : cached.data?.count;
  const currentPage = count === undefined ? page : clampPage(page, getTotalPages(count, pageSize));
  const isClamped = currentPage !== page;
  const clamped = useQuery({
    ...getQueryOptions(getOffset(currentPage, pageSize)),
    enabled: isClamped,
  });
  const newerClampedCount =
    isClamped && !clamped.isPlaceholderData && clamped.dataUpdatedAt > cached.dataUpdatedAt
      ? clamped.data?.count
      : undefined;
  const requested = useQuery({
    ...requestedOptions,
    enabled: (query) =>
      (typeof enabled === "function" ? enabled(query) : enabled) &&
      !isPastEnd(page, pageSize, newerClampedCount ?? query.state.data?.count),
  });

  return { page: currentPage, query: isClamped ? clamped : requested };
}
