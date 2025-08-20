import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { GetObjectsParams, OBJECTS_PER_PAGE, getObjects } from "./get-objects";

type GetObjectsQueryParams = Omit<GetObjectsParams, keyof PaginationParams>;

export function getObjectsInfiniteQueryOptions({
  schema,
  filters,
  branchName,
  atDate,
  getAttributesVisible,
  getRelationshipsVisible,
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
        getAttributesVisible,
        getRelationshipsVisible,
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

export function useObjects(params: Omit<GetObjectsQueryParams, keyof ContextParams>) {
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
