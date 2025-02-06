import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions } from "@tanstack/react-query";
import { OBJECTS_PER_PAGE, getActivitiesFromApi } from "./get-activities";

export function getActivitiesInfiniteQueryOptions() {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: ["activities"],
    queryFn: () => {
      return getActivitiesFromApi({
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}
