import {
  OBJECTS_PER_PAGE,
  ProposedChangesFromApiParams,
} from "@/entities/proposed-changes/api/get-proposed-changes-from-api";
import { PaginationParams } from "@/shared/api/types";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import { getProposedChanges } from "./get-proposed-changes";

type GetProposedChangesInfiniteQueryOptionsParams = Omit<
  ProposedChangesFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangesInfiniteQueryOptions({
  schema,
  filters,
  getAttributesVisible,
  getRelationshipsVisible,
}: GetProposedChangesInfiniteQueryOptionsParams) {
  return infiniteQueryOptions({
    queryKey: ["objects", schema.kind, filters],
    queryFn: ({ pageParam }) => {
      return getProposedChanges({
        schema,
        offset: pageParam,
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

export function useGetProposedChanges(params: GetProposedChangesInfiniteQueryOptionsParams) {
  return useInfiniteQuery(getProposedChangesInfiniteQueryOptions(params));
}
