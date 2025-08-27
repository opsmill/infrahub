import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { PROPOSED_CHANGE_THREAD } from "@/entities/proposed-changes/constants";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { ProposedChangeThreadFromApiParams } from "../api/get-proposed-change-thread-from-api";
import { getProposedChangeThread } from "./get-proposed-change-thread";

type GetProposedChangeThreadQueryOptionsParams = Omit<
  ProposedChangeThreadFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangeThreadQueryOptions({
  threadId,
  branchName,
  atDate,
}: GetProposedChangeThreadQueryOptionsParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "objects", PROPOSED_CHANGE_THREAD, threadId],
    queryFn: () => {
      return getProposedChangeThread({
        branchName,
        atDate,
        threadId,
      });
    },
  });
}

export function useGetProposedChangeThread(
  params: Omit<GetProposedChangeThreadQueryOptionsParams, keyof ContextParams>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getProposedChangeThreadQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
