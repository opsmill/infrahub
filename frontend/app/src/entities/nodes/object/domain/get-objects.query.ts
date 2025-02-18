import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { ContextParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { OBJECTS_PER_PAGE, getObjects } from "./get-objects";

type GetObjectsQueryParams = ContextParams & {
  schema: IModelSchema;
  filters?: Array<Filter>;
};

export function getObjectsInfiniteQueryOptions({
  schema,
  filters,
  branchName,
  atDate,
}: GetObjectsQueryParams) {
  return infiniteQueryOptions({
    queryKey: [branchName, atDate, "objects", schema.kind, JSON.stringify(filters)],
    queryFn: ({ pageParam }) => {
      return getObjects({
        schema,
        offset: pageParam,
        branchName,
        atDate,
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

export function useObjects(params: Omit<GetObjectsQueryParams, "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getObjectsInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
