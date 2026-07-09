import { graphql, type ResultOf, type VariablesOf } from "gql.tada";

import type { ActionAvailability } from "@/shared/api/graphql/generated/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const QUERY = graphql(`
  query actions($proposedChangeId: String!) {
    CoreProposedChangeAvailableActions(proposed_change_id: $proposedChangeId) {
      count
      edges {
        node {
          action
          available
          unavailability_reason
        }
      }
    }
  }
`);

export interface GetProposedChangeActionFromApiParams extends VariablesOf<typeof QUERY> {}

export const getProposedChangeAvailableActionFromApi = async ({
  proposedChangeId,
}: GetProposedChangeActionFromApiParams) => {
  return graphqlClient.query({
    query: QUERY,
    variables: {
      proposedChangeId,
    },
  });
};

export type ProposedChangeAvailableActions = Record<string, ActionAvailability>;

// Reshape the raw edge list into a record keyed by action (camel-cased for the
// draft/approve/reject actions the UI special-cases).
export function mapProposedChangeAvailableActions(
  data: ResultOf<typeof QUERY>
): ProposedChangeAvailableActions {
  return data.CoreProposedChangeAvailableActions.edges.reduce((acc, edge) => {
    if (edge.node.action === "set-draft") {
      return { ...acc, setDraft: edge.node };
    }

    if (edge.node.action === "unset-draft") {
      return { ...acc, unsetDraft: edge.node };
    }

    if (edge.node.action === "cancel-approve") {
      return { ...acc, cancelApprove: edge.node };
    }

    if (edge.node.action === "cancel-reject") {
      return { ...acc, cancelReject: edge.node };
    }

    return { ...acc, [edge.node.action]: edge.node };
  }, {});
}
