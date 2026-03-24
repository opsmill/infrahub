import { graphql, type VariablesOf } from "gql.tada";

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
