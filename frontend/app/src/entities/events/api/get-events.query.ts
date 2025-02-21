import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ContextParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { GlobalEventsFilters, OBJECTS_PER_PAGE, getEventsFromApi } from "./get-events-from-api";

export function getEventsQueryOptions({
  filters,
  branchName,
  atDate,
}: { filters: GlobalEventsFilters } & ContextParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, atDate, "events", filters],
    queryFn: ({ pageParam }) => {
      return getEventsFromApi({
        ...filters,
        offset: pageParam,
        branchName,
        atDate,
      });
    },
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
