import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetProposedChangeDetailsParams,
  getProposedChangeDetails,
} from "@/entities/proposed-changes/domain/get-proposed-change-details";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";

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
