import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getGlobalEventsFromApi } from "./get-global-events";

export function getEventsQueryOptions() {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["global-events"],
    queryFn: () => {
      return getGlobalEventsFromApi({
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useGlobalEvents = () => {
  return useQuery(getEventsQueryOptions());
};
