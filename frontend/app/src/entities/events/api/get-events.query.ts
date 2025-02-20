import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { GlobalEventsFilters, getEventsFromApi } from "./get-events-from-api";

export function getEventsQueryOptions(filters: GlobalEventsFilters) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events", filters],
    queryFn: () => {
      return getEventsFromApi({
        ...filters,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = (filters: GlobalEventsFilters) => {
  return useQuery(getEventsQueryOptions(filters));
};
