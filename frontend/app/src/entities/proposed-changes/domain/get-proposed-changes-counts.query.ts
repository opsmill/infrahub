import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import {
  GetProposedChangesCountsParams,
  getProposedChangesCounts,
} from "@/entities/proposed-changes/domain/get-proposed-changes-counts";
import { queryOptions, useQuery } from "@tanstack/react-query";

type GetProposedChangesCountsQueryOptionsParams = GetProposedChangesCountsParams;

export function getProposedChangesCountsQueryOptions({
  filters,
}: GetProposedChangesCountsQueryOptionsParams) {
  return queryOptions({
    queryKey: ["objects", PROPOSED_CHANGE_OBJECT, "count", filters],
    queryFn: () => {
      return getProposedChangesCounts({ filters });
    },
  });
}

export function useGetProposedChangesCounts(params: GetProposedChangesCountsQueryOptionsParams) {
  return useQuery(getProposedChangesCountsQueryOptions(params));
}
