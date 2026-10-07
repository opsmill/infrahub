import { hashKey, type QueryKey, type UseQueryOptions, useQuery } from "@tanstack/react-query";
import React from "react";

import { clampPage, getOffset, getTotalPages } from "@/shared/utils/table-pagination";

const clampToCount = (page: number, pageSize: number, count: number | undefined) =>
  count === undefined ? page : clampPage(page, getTotalPages(count, pageSize));

interface CountClampedQueryParams {
  page: number;
  pageSize: number;
}

interface ObservedCount {
  count: number;
  updatedAt: number;
}

const getNewerCount = (a: ObservedCount | undefined, b: ObservedCount | undefined) =>
  a && (!b || a.updatedAt >= b.updatedAt) ? a : b;

/**
 * Asks for the requested page, or for the last real page when the newest count puts the requested
 * one past the end.
 */
export function useCountClampedQuery<TData extends { count: number }, TKey extends QueryKey>(
  { page, pageSize }: CountClampedQueryParams,
  getQueryOptions: (offset: number) => UseQueryOptions<TData, Error, TData, TKey>
) {
  const requestedOptions = getQueryOptions(getOffset(page, pageSize));
  const requestedKey = hashKey(requestedOptions.queryKey);
  const { enabled = true } = requestedOptions;
  // Reads the requested page's cache without fetching, so the clamp is known before that fetch.
  const cached = useQuery({ ...requestedOptions, enabled: false });
  // The clamped page's key depends on this count, so its answer must outlive the key it came from.
  const [clampedCount, setClampedCount] = React.useState<
    ObservedCount & { requestedKey: string; page: number }
  >();
  const storedCount = clampedCount?.requestedKey === requestedKey ? clampedCount : undefined;
  // A placeholder count belongs to the row set before this one, so it cannot judge this page.
  const cachedCount =
    cached.data && !cached.isPlaceholderData
      ? { count: cached.data.count, updatedAt: cached.dataUpdatedAt }
      : undefined;
  const lastRealPage = clampToCount(page, pageSize, getNewerCount(cachedCount, storedCount)?.count);
  const isPastEnd = lastRealPage !== page;
  // The requested page's own answer predates the count that brought it back, so its rows are empty.
  const isRequestedOutdated =
    !isPastEnd && clampToCount(page, pageSize, cachedCount?.count) !== page;
  const currentPage = isRequestedOutdated && storedCount ? storedCount.page : lastRealPage;
  const isClamped = currentPage !== page;
  const clampedOptions = getQueryOptions(getOffset(currentPage, pageSize));
  const clamped = useQuery({
    ...clampedOptions,
    enabled: isClamped,
    // The previous window is past the end, so its rows would show this page as empty.
    placeholderData: undefined,
  });
  if (isClamped && clamped.data && clamped.dataUpdatedAt > (storedCount?.updatedAt ?? 0)) {
    setClampedCount({
      requestedKey,
      page: currentPage,
      count: clamped.data.count,
      updatedAt: clamped.dataUpdatedAt,
    });
  }
  const requested = useQuery({
    // Watching the clamped page makes its rows the placeholder for the next page, not the empty ones.
    ...(isPastEnd ? clampedOptions : requestedOptions),
    enabled: (query) => !isPastEnd && (typeof enabled === "function" ? enabled(query) : enabled),
    // Rows older than the newest count are out of date, whatever the stale time says.
    ...(isRequestedOutdated && { staleTime: 0 }),
  });

  return { page: currentPage, query: isClamped ? clamped : requested };
}
