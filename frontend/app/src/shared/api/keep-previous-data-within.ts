import { partialMatchKey, type QueryKey } from "@tanstack/react-query";

// Rows from another list or an empty page past the end would show under the wrong heading while loading.
export function keepPreviousDataWithin<TPage>(
  listKey: QueryKey,
  hasRows?: (page: TPage) => boolean
) {
  return <TData extends TPage>(
    previousData: TData | undefined,
    previousQuery?: { queryKey: QueryKey }
  ) =>
    previousData !== undefined &&
    previousQuery &&
    partialMatchKey(previousQuery.queryKey, listKey) &&
    (hasRows?.(previousData) ?? true)
      ? previousData
      : undefined;
}
