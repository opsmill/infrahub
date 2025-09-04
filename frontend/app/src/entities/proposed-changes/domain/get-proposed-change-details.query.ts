import {
  GetProposedChangeDetailsParams,
  getProposedChangeDetails,
} from "@/entities/proposed-changes/domain/get-proposed-change-details";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/domain/proposed-changes.query-keys";
import { queryOptions, useQuery } from "@tanstack/react-query";

type GetProposedChangeDetailsQueryOptionsParams = GetProposedChangeDetailsParams;

export function getProposedChangeDetailsQueryOptions({
  proposedChangeId,
}: GetProposedChangeDetailsQueryOptionsParams) {
  return queryOptions({
    queryKey: proposedChangesQueryKeys.detail(proposedChangeId),
    queryFn: () => {
      return getProposedChangeDetails({ proposedChangeId });
    },
  });
}

export function useGetProposedChangeDetails(params: GetProposedChangeDetailsQueryOptionsParams) {
  return useQuery(getProposedChangeDetailsQueryOptions(params));
}
