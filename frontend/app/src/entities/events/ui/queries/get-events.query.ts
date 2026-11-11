import { type InfiniteData, infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import type { InfiniteQueryConfig } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { EventType } from "@/entities/events/domain/model/event";
import { type GetEventsParams, getEvents } from "@/entities/events/domain/use-cases/get-events";

interface GetEventsQueryOptions extends GetEventsParams {}

// `shownAtBoundary` counts the events already shown whose time is the boundary, once they fill a page on their own.
type EventsPageParam = { boundary: string; shownAtBoundary: number } | undefined;

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

function continueFrom(filters: GetEventsParams, pageParam: EventsPageParam): GetEventsParams {
  if (pageParam === undefined) return filters;

  const { boundary, shownAtBoundary } = pageParam;
  const bounded =
    filters.order === "ASC" ? { ...filters, since: boundary } : { ...filters, until: boundary };

  return shownAtBoundary > 0 ? { ...bounded, offset: shownAtBoundary } : bounded;
}

function countShownAt(pages: Array<Array<EventType>>, boundary: string) {
  const shownIds = new Set<string>();

  for (const page of pages) {
    for (const event of page) {
      if (event.occurred_at === boundary) shownIds.add(event.id);
    }
  }

  return shownIds.size;
}

export function getEventsQueryOptions(filters: GetEventsParams) {
  const pageSize = filters.limit ?? DEFAULT_PAGE_SIZE;

  return infiniteQueryOptions({
    queryKey: ["events", filters],
    queryFn: ({ pageParam }) => getEvents(continueFrom(filters, pageParam)),
    initialPageParam: undefined as EventsPageParam,
    getNextPageParam: (lastPage, allPages, lastPageParam) => {
      const boundary = lastPage.at(-1)?.occurred_at;

      if (lastPage.length < pageSize || !boundary) return;

      if (boundary !== lastPageParam?.boundary) return { boundary, shownAtBoundary: 0 };

      // Every event of the page has the time it was asked up to, so the same request would return the same page.
      // The next request skips the events of that time already shown.
      const shownAtBoundary = countShownAt(allPages, boundary);

      // The server orders events of the same time arbitrarily, so a page can repeat events instead of adding new ones.
      if (shownAtBoundary === lastPageParam.shownAtBoundary) return;

      return { boundary, shownAtBoundary };
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
