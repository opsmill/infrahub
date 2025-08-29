import { ActionAvailability } from "@/shared/api/graphql/generated/graphql";
import {
  GetProposedChangeActionFromApiParams,
  getProposedChangeAvailableActionFromApi,
} from "../api/get-proposed-changes-available-actions-from-api";

export async function getProposedChangeAvailableActions(
  params: GetProposedChangeActionFromApiParams
) {
  const { data, errors } = await getProposedChangeAvailableActionFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
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
}
