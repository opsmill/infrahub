import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import {
  OBJECT_RELATIONSHIPS_PER_PAGE,
  getObjectRelationships,
} from "@/entities/nodes/relationships/domain/get-object-relationships/get-object-relationships";
import { ModelSchema } from "@/entities/schema/types";
import { Filter } from "@/shared/hooks/useFilters";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

export type UseObjectRelationshipsParams = {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  filters?: Array<Filter>;
};

export function getObjectRelationshipsQueryOptions({
  parentKind,
  parentId,
  relationshipName,
  relationshipSchema,
  filters,
}: UseObjectRelationshipsParams) {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return infiniteQueryOptions({
    queryKey: [
      currentBranchName,
      timeMachineDate,
      "objects",
      parentKind,
      parentId,
      relationshipSchema.kind,
      filters,
    ],
    queryFn: ({ pageParam }) => {
      return getObjectRelationships({
        parentKind,
        parentId,
        relationshipName,
        relationshipSchema,
        offset: pageParam,
        branchName: currentBranchName,
        atDate: timeMachineDate,
        filters,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < OBJECT_RELATIONSHIPS_PER_PAGE) {
        return undefined;
      }
      return lastPageParam + OBJECT_RELATIONSHIPS_PER_PAGE;
    },
  });
}

export function useObjectRelationships(params: UseObjectRelationshipsParams) {
  return useInfiniteQuery(getObjectRelationshipsQueryOptions(params));
}
