import { partialMatchKey, type QueryKey } from "@tanstack/react-query";

// Rows from another list, such as another branch, would show under the wrong heading while loading.
export function keepPreviousDataWithin(listKey: QueryKey) {
  return <TData>(previousData: TData | undefined, previousQuery?: { queryKey: QueryKey }) =>
    previousQuery && partialMatchKey(previousQuery.queryKey, listKey) ? previousData : undefined;
}
