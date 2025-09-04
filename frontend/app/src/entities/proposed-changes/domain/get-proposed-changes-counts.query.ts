import {
  GetProposedChangesCountsParams,
  getProposedChangesCounts,
} from "@/entities/proposed-changes/domain/get-proposed-changes-counts";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/domain/proposed-changes.query-keys";
import { queryOptions, useQuery } from "@tanstack/react-query";

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
