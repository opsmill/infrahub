import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetProposedChangeAvailableActionsParams,
  getProposedChangeAvailableActions,
} from "@/entities/proposed-changes/domain/get-proposed-change-available-actions";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/domain/proposed-changes.query-keys";

export type GetProposedChangeAvailableActionsQueryOptionsParams =
  GetProposedChangeAvailableActionsParams;

export function getProposedChangeAvailableActionsQueryOptions({
  proposedChangeId,
}: GetProposedChangeAvailableActionsQueryOptionsParams) {
  return queryOptions({
    queryKey: proposedChangesQueryKeys.actions(proposedChangeId),
    queryFn: () => {
      return getProposedChangeAvailableActions({ proposedChangeId });
    },
  });
}

export function useGetProposedChangeAvailableActions(
  params: GetProposedChangeAvailableActionsQueryOptionsParams
) {
  return useQuery(getProposedChangeAvailableActionsQueryOptions(params));
}
