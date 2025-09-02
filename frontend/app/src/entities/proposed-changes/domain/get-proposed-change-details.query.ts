import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { queryOptions, useQuery } from "@tanstack/react-query";
import {
  GetProposedChangeDetailsParams,
  getProposedChangeDetails,
} from "./get-proposed-change-details";

type GetProposedChangeDetailsQueryOptionsParams = GetProposedChangeDetailsParams;

export function getProposedChangeDetailsQueryOptions({
  proposedChangeId,
}: GetProposedChangeDetailsQueryOptionsParams) {
  return queryOptions({
    queryKey: ["objects", PROPOSED_CHANGE_OBJECT, proposedChangeId],
    queryFn: () => {
      return getProposedChangeDetails({ proposedChangeId });
    },
  });
}

export function useGetProposedChangeDetails(params: GetProposedChangeDetailsQueryOptionsParams) {
  return useQuery(getProposedChangeDetailsQueryOptions(params));
}
