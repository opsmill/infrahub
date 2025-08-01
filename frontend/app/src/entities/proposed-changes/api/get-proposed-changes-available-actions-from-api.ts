import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

export interface GetProposedChangeActionFromApiParams extends Omit<ContextParams, "branchName"> {}

const query = gql`
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
`;

const mock = {
  data: {
    CoreProposedChangeAvailableActions: {
      count: 5,
      edges: [
        {
          node: {
            action: "open",
            available: true,
            unavailability_reason: null,
          },
        },
        {
          node: {
            action: "close",
            available: false,
            unavailability_reason: "The proposed change state is not open",
          },
        },
        {
          node: {
            action: "setDraft",
            available: false,
            unavailability_reason: "The proposed change state is not open",
          },
        },
        {
          node: {
            action: "approve",
            available: false,
            unavailability_reason: "The proposed change state is not open",
          },
        },
        {
          node: {
            action: "reject",
            available: false,
            unavailability_reason: "The proposed change state is not open",
          },
        },
        {
          node: {
            action: "merge",
            available: true,
            unavailability_reason: "The proposed change state is not open",
          },
        },
      ],
    },
  },
};

export const getProposedChangeAvailableActionFromApi = async ({
  atDate,
}: GetProposedChangeActionFromApiParams) => {
  return mock;
  return graphqlClient.query({
    query,
    context: {
      date: atDate,
    },
  });
};
