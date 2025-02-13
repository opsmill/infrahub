import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getEventsFromApi } from "./get-events";

export function getEventsQueryOptions({
  ids,
  limit,
}: { ids?: Array<string | undefined>; limit?: number }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events", ids],
    queryFn: () => {
      return getEventsFromApi({
        ids,
        limit,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = ({
  ids = [],
  limit,
}: { ids?: Array<string | undefined>; limit?: number }) => {
  return useQuery(getEventsQueryOptions({ ids, limit }));
};
