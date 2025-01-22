import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions } from "@tanstack/react-query";
import { OBJECTS_PER_PAGE, getObjects } from "./get-objects";

export function getObjectsInfiniteQueryOptions({ schema }: { schema: IModelSchema }) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: [currentBranchName, timeMachineDate, schema.kind],
    queryFn: ({ pageParam }) => getObjects({ schema, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + OBJECTS_PER_PAGE;
    },
  });
}
