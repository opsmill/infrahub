import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ProposedChangesCountsFromApiParams } from "@/entities/proposed-changes/api/get-proposed-changes-counts-from-api";
import { getProposedChangesCounts } from "@/entities/proposed-changes/domain/get-proposed-changes-counts";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/utils/constant";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

type GetObjectsQueryParams = Omit<ProposedChangesCountsFromApiParams, keyof PaginationParams>;

export function getProposedChangesCountsQueryOptions({
  branchName,
  atDate,
  filters,
}: GetObjectsQueryParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "objects", PROPOSED_CHANGE_OBJECT, filters, "count"],
    queryFn: () => {
      return getProposedChangesCounts({
        branchName,
        atDate,
        filters,
      });
    },
  });
}

export function useProposedChangesCounts(params: Omit<GetObjectsQueryParams, keyof ContextParams>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getProposedChangesCountsQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
