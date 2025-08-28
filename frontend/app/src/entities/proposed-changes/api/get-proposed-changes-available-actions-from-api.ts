import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

export interface GetProposedChangeActionFromApiParams extends Omit<ContextParams, "branchName"> {
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
  atDate,
}: GetProposedChangeActionFromApiParams) => {
  return graphqlClient.query({
    query,
    variables: {
      proposedChangeId,
    },
    context: {
      date: atDate,
    },
  });
};
