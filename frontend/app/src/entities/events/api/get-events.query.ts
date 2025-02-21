import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { GlobalEventsFilters, OBJECTS_PER_PAGE, getEventsFromApi } from "./get-events-from-api";

export function getEventsQueryOptions({ filters }: { filters: GlobalEventsFilters }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: ["events", filters],
    queryFn: ({ pageParam }) => {
      return getEventsFromApi({
        ...filters,
        offset: pageParam,
        branchName: currentBranchName,
        atDate: timeMachineDate,
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
  return useInfiniteQuery(getEventsQueryOptions({ filters }));
};
