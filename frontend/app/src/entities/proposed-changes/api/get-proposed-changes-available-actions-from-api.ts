import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export interface GetProposedChangeActionFromApiParams {
  proposedChangeId: string;
}

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

export const getProposedChangeAvailableActionFromApi = async ({
  proposedChangeId,
}: GetProposedChangeActionFromApiParams) => {
  return graphqlClient.query({
    query,
    variables: {
      proposedChangeId,
    },
  });
};
