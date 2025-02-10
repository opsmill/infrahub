import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { getActivitiesFromApi } from "./get-activities";

export function getActivitiesQueryOptions({ ids }: { ids?: Array<string> }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return queryOptions({
    queryKey: ["activities"],
    queryFn: () => {
      return getActivitiesFromApi({
        ids,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
  });
}

export const useActivities = ({ ids }: { ids?: Array<string> }) => {
  return useQuery(getActivitiesQueryOptions({ ids }));
};
