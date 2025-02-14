import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getEventsFromApi } from "./get-events";

export function getEventsQueryOptions({
  ids,
  offset,
  limit,
}: { ids?: Array<string | undefined>; offset?: number; limit?: number }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["events", ids, offset, limit],
    queryFn: () => {
      return getEventsFromApi({
        ids,
        offset,
        limit,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEvents = ({
  ids = [],
  offset,
  limit,
}: { ids?: Array<string | undefined>; offset?: number; limit?: number }) => {
  return useQuery(getEventsQueryOptions({ ids, offset, limit }));
};
