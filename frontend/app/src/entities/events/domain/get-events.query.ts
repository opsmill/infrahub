import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { type GetEventsParams, getEvents } from "@/entities/events/domain/get-events";

interface GetEventsQueryOptions extends GetEventsParams {}

export function getEventsQueryOptions(filters: GetEventsParams) {
  return infiniteQueryOptions({
    queryKey: ["events", filters],
    queryFn: ({ pageParam }) =>
      getEvents({
        ...filters,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < DEFAULT_PAGE_SIZE) {
        return;
      }
      return lastPageParam + DEFAULT_PAGE_SIZE;
    },
  });
}

export function useGetEvents(
  filters: GetEventsQueryOptions,
  config?: InfiniteQueryConfig<typeof getEventsQueryOptions>
) {
  return useInfiniteQuery({
    ...getEventsQueryOptions(filters),
    ...config,
  });
}
