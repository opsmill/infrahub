import { OBJECTS_PER_PAGE } from "@/entities/events/api/get-events-from-api";
import { GetEventsParams, getEvents } from "@/entities/events/domain/get-events";
import {
  UseInfiniteQueryOptions,
  infiniteQueryOptions,
  useInfiniteQuery,
} from "@tanstack/react-query";

interface GetEventsQueryOptions extends GetEventsParams {
  queryOptions: Omit<
    UseInfiniteQueryOptions,
    "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
  >;
}

export function getEventsQueryOptions({ filters, queryOptions }: GetEventsQueryOptions) {
  return infiniteQueryOptions({
    ...queryOptions,
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
  return useInfiniteQuery(getEventsQueryOptions({ filters, queryOptions }));
}
