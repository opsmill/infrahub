import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getEventDetailsFromApi } from "./get-event-details-from-api";

export function getEventDetailsQueryOptions({ id }: { id: string }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["event-details", id],
    queryFn: () => {
      return getEventDetailsFromApi({
        id,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useEventDetails = ({ id }: { id: string }) => {
  return useQuery(getEventDetailsQueryOptions({ id }));
};
