import { partialMatchKey, type QueryKey } from "@tanstack/react-query";

// Rows from another list, such as another branch, would show under the wrong heading while loading.
// A page without rows, such as one past the end, is not kept either: it would show as an empty
// table until the page the user went to arrives.
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
