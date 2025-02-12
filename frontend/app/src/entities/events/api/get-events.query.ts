import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getEventsFromApi } from "./get-events";

export function getEventsQueryOptions({ ids }: { ids?: Array<string | undefined> }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events"],
    queryFn: () => {
      return getEventsFromApi({
        ids,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = ({ ids = [] }: { ids?: Array<string | undefined> }) => {
  return useQuery(getEventsQueryOptions({ ids }));
};
