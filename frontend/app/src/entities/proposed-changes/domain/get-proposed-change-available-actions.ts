import type { ActionAvailability } from "@/shared/api/graphql/generated/graphql";

import {
  type GetProposedChangeActionFromApiParams,
  getProposedChangeAvailableActionFromApi,
} from "@/entities/proposed-changes/api/get-proposed-changes-available-actions-from-api";

export type GetProposedChangeAvailableActionsParams = GetProposedChangeActionFromApiParams;

export type GetProposedChangeAvailableActions = (
  params: GetProposedChangeAvailableActionsParams
) => Promise<Record<string, ActionAvailability>>;

export const getProposedChangeAvailableActions: GetProposedChangeAvailableActions = async (
  params: GetProposedChangeActionFromApiParams
) => {
  const { data, errors } = await getProposedChangeAvailableActionFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.CoreProposedChangeAvailableActions.edges.reduce(
    (acc: Record<string, ActionAvailability>, edge: { node: ActionAvailability }) => {
      if (edge.node.action === "set-draft") {
        return {
          ...acc,
          setDraft: edge.node,
        };
      }

      if (edge.node.action === "unset-draft") {
        return {
          ...acc,
          unsetDraft: edge.node,
        };
      }

      if (edge.node.action === "cancel-approve") {
        return {
          ...acc,
          cancelApprove: edge.node,
        };
      }

      if (edge.node.action === "cancel-reject") {
        return {
          ...acc,
          cancelReject: edge.node,
        };
      }

      return {
        ...acc,
        [edge.node.action]: edge.node,
      };
    },
    {}
  );
};
