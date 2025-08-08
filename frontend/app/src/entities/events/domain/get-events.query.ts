import { OBJECTS_PER_PAGE } from "@/entities/events/api/get-events-from-api";
import { GetEventsParams, getEvents } from "@/entities/events/domain/get-events";
import { QueryConfig } from "@/shared/api/types";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

interface GetEventsQueryOptions extends GetEventsParams {
  queryOptions: QueryConfig<typeof getEventsQueryOptions>;
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
        return undefined;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}

export function useGetEvents({ filters, queryOptions }: GetEventsQueryOptions) {
  return useInfiniteQuery({
    ...getEventsQueryOptions({ filters }),
    ...queryOptions,
  });
}
