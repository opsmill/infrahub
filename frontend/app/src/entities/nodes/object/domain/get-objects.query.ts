import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectsParams,
  getObjects,
  OBJECTS_PER_PAGE,
} from "@/entities/nodes/object/domain/get-objects";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

type GetObjectsQueryParams = Omit<GetObjectsParams, keyof PaginationParams>;

export function getObjectsInfiniteQueryOptions(params: GetObjectsQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.list({ ...params, objectKind: params.schema.kind! }),
    queryFn: ({ pageParam }) => {
      return getObjects({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECTS_PER_PAGE) {
        return;
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
