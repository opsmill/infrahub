import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_VALIDATORS = gql`
  query GET_CORE_VALIDATORS($id: ID!) {
    CoreValidator(proposed_change__ids: [$id]) {
      edges {
        node {
          id
          display_label
          conclusion {
            value
          }
          started_at {
            value
          }
          completed_at {
            value
          }
          state {
            value
          }
          checks {
            edges {
              node {
                conclusion {
                  value
                }
                severity {
                  value
                }
              }
            }
          }
          __typename
        }
      }
    }
  }
`;

export interface GetValidatorsFromApiParams {
  proposedChangeId: string;
}

export const getValidatorsFromApi = async ({ proposedChangeId }: GetValidatorsFromApiParams) => {
  return graphqlClient.query({
    query: GET_VALIDATORS,
    variables: {
      id: proposedChangeId,
    },
  });
};
