import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
  OBJECTS_PER_PAGE,
  ProposedChangesFromApiParams,
} from "../api/get-proposed-changes-from-api";
import { getProposedChanges } from "./get-proposed-changes";

type GetObjectsQueryParams = Omit<ProposedChangesFromApiParams, keyof PaginationParams>;

export function getProposedChangesInfiniteQueryOptions({
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
      return getProposedChanges({
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

export function useProposedChanges(params: Omit<GetObjectsQueryParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useInfiniteQuery(
    getProposedChangesInfiniteQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
