import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { EventType } from "@/entities/events/domain/model/event";
import { type GetEventsParams, getEvents } from "@/entities/events/domain/use-cases/get-events";

import { generateEvent } from "../../../../../tests/fake/event";
import { getEventsQueryOptions } from "./get-events.query";

vi.mock("@/entities/events/domain/use-cases/get-events", () => ({ getEvents: vi.fn() }));

const getEventsMock = vi.mocked(getEvents);

function occurredAt(microsecond: number) {
  return `2026-10-04T12:00:00.${String(microsecond).padStart(6, "0")}+00:00`;
}

function eventsFrom(prefix: string, times: Array<number>): Array<EventType> {
  return times.map((time, index) =>
    generateEvent({ id: `${prefix}-${index}`, occurred_at: occurredAt(time) })
  );
}

function countDown(from: number, count: number) {
  return Array.from({ length: count }, (_, index) => from - index);
}

function countUp(from: number, count: number) {
  return Array.from({ length: count }, (_, index) => from + index);
}

function fetchPages(filters: GetEventsParams, pages: number) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return queryClient.fetchInfiniteQuery({ ...getEventsQueryOptions(filters), pages });
}

describe("getEventsQueryOptions", () => {
  beforeEach(() => {
    getEventsMock.mockReset();
    getEventsMock.mockResolvedValue([]);
  });

  it("asks for the next page up to the time of the oldest event shown, without an offset", async () => {
    // GIVEN
    const firstPage = eventsFrom("first", countDown(1000, DEFAULT_PAGE_SIZE));
    getEventsMock
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(eventsFrom("second", countDown(900, DEFAULT_PAGE_SIZE)));

    // WHEN
    await fetchPages({ level: 0 }, 2);

    // THEN
    expect(getEventsMock).toHaveBeenCalledTimes(2);
    expect(getEventsMock.mock.calls[1]?.[0]).toEqual({
      level: 0,
      until: firstPage.at(-1)?.occurred_at,
    });
    expect(getEventsMock.mock.calls[1]?.[0]).not.toHaveProperty("offset");
  });

  it("starts the first page from the time bound the caller set", async () => {
    // GIVEN
    const until = occurredAt(500);
    getEventsMock.mockResolvedValueOnce([]);

    // WHEN
    await fetchPages({ level: 0, until }, 1);

    // THEN
    expect(getEventsMock).toHaveBeenCalledWith({ level: 0, until });
  });

  it("drops the events of the next page that were already shown at the boundary", async () => {
    // GIVEN
    const tiedTime = 62;
    const firstPage = [
      ...eventsFrom("first", countDown(100, DEFAULT_PAGE_SIZE - 2)),
      generateEvent({ id: "tied-a", occurred_at: occurredAt(tiedTime) }),
      generateEvent({ id: "tied-b", occurred_at: occurredAt(tiedTime) }),
    ];
    const secondPage = [
      generateEvent({ id: "tied-a", occurred_at: occurredAt(tiedTime) }),
      generateEvent({ id: "tied-b", occurred_at: occurredAt(tiedTime) }),
      generateEvent({ id: "tied-c", occurred_at: occurredAt(tiedTime) }),
      ...eventsFrom("second", countDown(tiedTime - 1, DEFAULT_PAGE_SIZE - 3)),
    ];
    getEventsMock.mockResolvedValueOnce(firstPage).mockResolvedValueOnce(secondPage);
    const data = await fetchPages({ level: 0 }, 2);

    // WHEN
    const shown = getEventsQueryOptions({ level: 0 }).select?.(data);

    // THEN
    expect(shown?.pages[0]).toEqual(firstPage);
    expect(shown?.pages[1]?.map((event) => event.id)).toEqual(
      secondPage.slice(2).map((event) => event.id)
    );
  });

  it("stops paging when a page is shorter than the page size", async () => {
    // GIVEN
    getEventsMock.mockResolvedValueOnce(eventsFrom("first", countDown(1000, 10)));

    // WHEN
    await fetchPages({ level: 0 }, 2);

    // THEN
    expect(getEventsMock).toHaveBeenCalledTimes(1);
  });

  it("stops paging when every event of a full page shares the time it was asked up to", async () => {
    // GIVEN
    const firstPage = eventsFrom("first", countDown(1000, DEFAULT_PAGE_SIZE));
    const boundary = 1000 - DEFAULT_PAGE_SIZE + 1;
    getEventsMock
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(eventsFrom("tied", Array(DEFAULT_PAGE_SIZE).fill(boundary)));

    // WHEN
    await fetchPages({ level: 0 }, 3);

    // THEN
    expect(getEventsMock).toHaveBeenCalledTimes(2);
  });

  it("asks for the next page from the time of the newest event shown when the order is ascending", async () => {
    // GIVEN
    const firstPage = eventsFrom("first", countUp(100, DEFAULT_PAGE_SIZE));
    getEventsMock
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(eventsFrom("second", countUp(200, DEFAULT_PAGE_SIZE)));

    // WHEN
    await fetchPages({ order: "ASC" }, 2);

    // THEN
    expect(getEventsMock.mock.calls[1]?.[0]).toEqual({
      order: "ASC",
      since: firstPage.at(-1)?.occurred_at,
    });
  });
});
