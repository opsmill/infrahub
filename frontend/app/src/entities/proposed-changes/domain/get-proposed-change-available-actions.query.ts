import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { queryOptions, useQuery } from "@tanstack/react-query";
import {
  GetProposedChangeAvailableActionsParams,
  getProposedChangeAvailableActions,
} from "./get-proposed-change-available-actions";

export type GetProposedChangeAvailableActionsQueryOptionsParams =
  GetProposedChangeAvailableActionsParams;

export function getProposedChangeAvailableActionsQueryOptions({
  proposedChangeId,
}: GetProposedChangeAvailableActionsQueryOptionsParams) {
  return queryOptions({
    queryKey: ["objects", PROPOSED_CHANGE_OBJECT, proposedChangeId, "actions"],
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
