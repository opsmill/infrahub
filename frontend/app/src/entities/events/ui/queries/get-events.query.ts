import { type InfiniteData, infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { EventType } from "@/entities/events/domain/model/event";
import { type GetEventsParams, getEvents } from "@/entities/events/domain/use-cases/get-events";

interface GetEventsQueryOptions extends GetEventsParams {}

type EventsPageParam = string | undefined;

// The time bound is inclusive, so each page repeats the events at the boundary that the page before it already holds.
function dropRepeatedEvents(data: InfiniteData<Array<EventType>, EventsPageParam>) {
  const shownIds = new Set<string>();

  return {
    ...data,
    pages: data.pages.map((page) =>
      page.filter((event) => {
        if (shownIds.has(event.id)) return false;

        shownIds.add(event.id);
        return true;
      })
    ),
  };
}

function continueFrom(filters: GetEventsParams, boundary: EventsPageParam): GetEventsParams {
  if (boundary === undefined) return filters;

  return filters.order === "ASC"
    ? { ...filters, since: boundary }
    : { ...filters, until: boundary };
}

export function getEventsQueryOptions(filters: GetEventsParams) {
  const pageSize = filters.limit ?? DEFAULT_PAGE_SIZE;

  return infiniteQueryOptions({
    queryKey: ["events", filters],
    queryFn: ({ pageParam }) => getEvents(continueFrom(filters, pageParam)),
    initialPageParam: undefined as EventsPageParam,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      const boundary = lastPage.at(-1)?.occurred_at;

      // The server orders events of the same time arbitrarily, so a full page of one time would come back unchanged.
      if (lastPage.length < pageSize || !boundary || boundary === lastPageParam) {
        return;
      }

      return boundary;
    },
    select: dropRepeatedEvents,
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
