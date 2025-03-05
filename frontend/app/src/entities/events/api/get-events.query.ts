import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { EventType } from "react-hook-form";
import { getEvents } from "../domain/get-events";
import { GlobalEventsFilters, OBJECTS_PER_PAGE } from "./get-events-from-api";

export function getEventsQueryOptions({
  filters,
  branchName,
  atDate,
}: { filters: GlobalEventsFilters } & ContextParams) {
  return infiniteQueryOptions<Array<EventType>>({
    queryKey: [branchName, atDate, "events", filters],
    queryFn: ({ pageParam }) =>
      getEvents({
        filters,
        offset: pageParam,
        branchName,
        atDate,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage?.length < OBJECTS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}

export const useEvents = ({ filters }: { filters: GlobalEventsFilters }) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getEventsQueryOptions({ filters, branchName: currentBranch.name, atDate: timeMachineDate })
  );
};
