/**
 * Pagination configuration and utilities for dynamic page sizing.
 *
 * The pagination strategy works as follows:
 * - First page always uses DEFAULT_PAGE_SIZE (40) to avoid prefetching count
 * - Once the first page response includes the total count, we calculate the dynamic page size
 * - For datasets < DYNAMIC_PAGINATION_THRESHOLD (1000), we continue using DEFAULT_PAGE_SIZE
 * - For datasets >= DYNAMIC_PAGINATION_THRESHOLD, we use DYNAMIC_PAGINATION_PERCENTAGE (5%) of total
 * - The calculated page size is clamped between MIN_PAGE_SIZE and MAX_PAGE_SIZE
 * - The page size is locked after the first calculation for consistent scroll behavior
 */

/** Default page size used for the first page and small datasets */
export const DEFAULT_PAGE_SIZE = 40;

/** Minimum page size even for dynamic pagination */
export const MIN_PAGE_SIZE = 40;

/** Maximum page size to prevent overly large fetches */
export const MAX_PAGE_SIZE = 200;

/** Threshold above which dynamic pagination is applied */
export const DYNAMIC_PAGINATION_THRESHOLD = 1000;

/** Percentage of total items to fetch per page when using dynamic pagination */
export const DYNAMIC_PAGINATION_PERCENTAGE = 0.05;

/**
 * Calculates the dynamic page size based on total count.
 *
 * @param totalCount - The total number of items available
 * @returns The calculated page size, or DEFAULT_PAGE_SIZE for small datasets
 *
 * @example
 * calculateDynamicPageSize(500)   // Returns 40 (below threshold)
 * calculateDynamicPageSize(1000)  // Returns 50 (5% of 1000)
 * calculateDynamicPageSize(2000)  // Returns 100 (5% of 2000)
 * calculateDynamicPageSize(10000) // Returns 200 (capped at MAX_PAGE_SIZE)
 */
export function calculateDynamicPageSize(totalCount: number): number {
  if (totalCount < DYNAMIC_PAGINATION_THRESHOLD) {
    return DEFAULT_PAGE_SIZE;
  }

  const dynamicSize = Math.ceil(totalCount * DYNAMIC_PAGINATION_PERCENTAGE);
  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, dynamicSize));
}

/**
 * Type for paginated response that includes count.
 * Used by API functions to return both items and total count.
 */
export interface PaginatedResponse<T> {
  items: T[];
  count: number;
}

/**
 * Creates a getNextPageParam function for TanStack Query infinite queries
 * that uses dynamic pagination based on total count from the first page.
 *
 * @param defaultPageSize - The page size used for the first fetch (default: DEFAULT_PAGE_SIZE)
 * @returns A getNextPageParam function for use with infiniteQueryOptions
 *
 * @example
 * infiniteQueryOptions({
 *   queryFn: ({ pageParam }) => fetchItems({ offset: pageParam.offset, limit: pageParam.limit }),
 *   initialPageParam: { offset: 0, limit: DEFAULT_PAGE_SIZE },
 *   getNextPageParam: createDynamicGetNextPageParam(),
 * })
 */
export function createDynamicGetNextPageParam<T extends PaginatedResponse<unknown>>(
  defaultPageSize: number = DEFAULT_PAGE_SIZE
) {
  return (
    lastPage: T,
    allPages: T[],
    lastPageParam: { offset: number; limit: number }
  ): { offset: number; limit: number } | undefined => {
    // If we got fewer items than requested, there are no more pages
    if (lastPage.items.length < lastPageParam.limit) {
      return;
    }

    // Get count from the first page (it's the same across all pages)
    const totalCount = allPages[0]?.count ?? 0;

    // Calculate page size: use dynamic sizing only after first page and if we have a count
    // The page size is effectively "locked" because we always derive it from allPages[0].count
    const pageSize = totalCount > 0 ? calculateDynamicPageSize(totalCount) : defaultPageSize;

    return {
      offset: lastPageParam.offset + lastPageParam.limit,
      limit: pageSize,
    };
  };
}

/**
 * Creates a simple getNextPageParam function for cases where the API
 * returns an array directly (legacy pattern) and we want to add dynamic pagination.
 *
 * This variant extracts count from a separate property in the response and
 * works with the existing pattern where pageParam is just an offset number.
 *
 * @param defaultPageSize - The page size used for comparisons (default: DEFAULT_PAGE_SIZE)
 * @returns A getNextPageParam function compatible with existing infinite query patterns
 */
export function createSimpleDynamicGetNextPageParam<T>(
  defaultPageSize: number = DEFAULT_PAGE_SIZE
) {
  let lockedPageSize: number | null = null;

  return (
    lastPage: { items: T[]; count: number },
    allPages: { items: T[]; count: number }[],
    lastPageParam: number
  ): number | undefined => {
    // Determine current page size based on what was fetched
    const currentPageSize = lockedPageSize ?? defaultPageSize;

    // If we got fewer items than the page size, there are no more pages
    if (lastPage.items.length < currentPageSize) {
      return;
    }

    // Lock page size after first page if not already locked
    if (lockedPageSize === null && allPages.length > 0 && allPages[0]) {
      const totalCount = allPages[0].count;
      lockedPageSize = calculateDynamicPageSize(totalCount);
    }

    return lastPageParam + (lockedPageSize ?? defaultPageSize);
  };
}
