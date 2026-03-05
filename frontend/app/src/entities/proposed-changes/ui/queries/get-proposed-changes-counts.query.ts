import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetProposedChangesCountsParams,
  getProposedChangesCounts,
} from "@/entities/proposed-changes/domain/get-proposed-changes-counts";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";

type GetProposedChangesCountsQueryOptionsParams = GetProposedChangesCountsParams;

export function getProposedChangesCountsQueryOptions(
  params: GetProposedChangesCountsQueryOptionsParams
) {
  return queryOptions({
    queryKey: proposedChangesQueryKeys.count(params),
    queryFn: () => {
      return getProposedChangesCounts(params);
    },
  });
}

export function useGetProposedChangesCounts(params: GetProposedChangesCountsQueryOptionsParams) {
  return useQuery(getProposedChangesCountsQueryOptions(params));
}
