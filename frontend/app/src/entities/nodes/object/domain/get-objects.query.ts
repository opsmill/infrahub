import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { Filter } from "@/shared/hooks/useFilters";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions } from "@tanstack/react-query";
import { OBJECTS_PER_PAGE, getObjects } from "./get-objects";

export function getObjectsInfiniteQueryOptions({
  schema,
  filters,
}: { schema: IModelSchema; filters?: Array<Filter> }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: ["objects", schema.kind, currentBranchName, timeMachineDate, JSON.stringify(filters)],
    queryFn: ({ pageParam }) => {
      return getObjects({
        schema,
        offset: pageParam,
        branchName: currentBranchName,
        atDate: timeMachineDate,
        filters,
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
