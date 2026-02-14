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
