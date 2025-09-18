import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ProposedChangeThreadFromApiParams } from "@/entities/proposed-changes/api/get-proposed-change-thread-from-api";
import { getProposedChangeThread } from "@/entities/proposed-changes/domain/get-proposed-change-thread";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/domain/proposed-changes.query-keys";

type GetProposedChangeThreadQueryOptionsParams = ProposedChangeThreadFromApiParams;

export function getProposedChangeThreadQueryOptions({
  threadId,
}: GetProposedChangeThreadQueryOptionsParams) {
  return queryOptions({
    queryKey: proposedChangesQueryKeys.thread(threadId),
    queryFn: () => {
      return getProposedChangeThread({ threadId });
    },
  });
}

export function useGetProposedChangeThread(params: GetProposedChangeThreadQueryOptionsParams) {
  return useQuery(getProposedChangeThreadQueryOptions(params));
}
