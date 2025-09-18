import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";

import { OBJECTS_PER_PAGE } from "@/entities/events/api/get-events-from-api";
import { type GetEventsParams, getEvents } from "@/entities/events/domain/get-events";

interface GetEventsQueryOptions extends GetEventsParams {
  config?: InfiniteQueryConfig<typeof getEventsQueryOptions>;
}

export function getEventsQueryOptions({ filters }: GetEventsParams) {
  return infiniteQueryOptions({
    queryKey: ["events", filters],
    queryFn: ({ pageParam }) =>
      getEvents({
        filters,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}

export function useGetEvents({ filters, config }: GetEventsQueryOptions) {
  return useInfiniteQuery({
    ...getEventsQueryOptions({ filters }),
    ...config,
  });
}
