import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, InfiniteQueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectChildren } from "@/entities/nodes/hierarchy/domain/get-object-children";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface ObjectChildrenQueryParams extends ContextParams {
  objectKind: string;
  parentObjectId: string | null;
}

export function getObjectChildrenInfiniteQueryOptions({
  branchName,
  atDate,
  objectKind,
  parentObjectId,
}: ObjectChildrenQueryParams) {
  return infiniteQueryOptions({
    queryKey: objectQueryKeys.tree({
      branchName,
      atDate,
      objectKind,
      objectId: parentObjectId,
    }),
    queryFn: async ({ pageParam }) => {
      return getObjectChildren({
        objectKind,
        parentObjectId,
        branchName,
        atDate,
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

export type UseGetObjectChildrenQueryConfig = InfiniteQueryConfig<
  typeof getObjectChildrenInfiniteQueryOptions
>;

export function useGetObjectChildren(
  params: Omit<ObjectChildrenQueryParams, keyof ContextParams>,
  config?: UseGetObjectChildrenQueryConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery({
    ...getObjectChildrenInfiniteQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
