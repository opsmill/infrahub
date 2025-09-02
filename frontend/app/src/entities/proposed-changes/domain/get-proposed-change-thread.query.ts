import { ProposedChangeThreadFromApiParams } from "@/entities/proposed-changes/api/get-proposed-change-thread-from-api";
import { PROPOSED_CHANGE_THREAD } from "@/entities/proposed-changes/constants";
import { getProposedChangeThread } from "@/entities/proposed-changes/domain/get-proposed-change-thread";
import { PaginationParams } from "@/shared/api/types";
import { queryOptions, useQuery } from "@tanstack/react-query";

type GetProposedChangeThreadQueryOptionsParams = Omit<
  ProposedChangeThreadFromApiParams,
  keyof PaginationParams
>;

export function getProposedChangeThreadQueryOptions({
  threadId,
}: GetProposedChangeThreadQueryOptionsParams) {
  return queryOptions({
    queryKey: ["objects", PROPOSED_CHANGE_THREAD, threadId],
    queryFn: () => {
      return getProposedChangeThread({ threadId });
    },
  });
}

export function useGetProposedChangeThread(params: GetProposedChangeThreadQueryOptionsParams) {
  return useQuery(getProposedChangeThreadQueryOptions(params));
}
