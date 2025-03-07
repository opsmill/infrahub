import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ContextParams } from "@/shared/api/types";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { getEvents } from "../domain/get-events";
import { GlobalEventsFilters, OBJECTS_PER_PAGE } from "./get-events-from-api";

export function getEventsQueryOptions({
  filters,
  branchName,
}: { filters: GlobalEventsFilters } & ContextParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, "events", filters],
    queryFn: ({ pageParam }) =>
      getEvents({
        filters,
        offset: pageParam,
        branchName,
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

  return useInfiniteQuery(getEventsQueryOptions({ filters, branchName: currentBranch.name }));
};
