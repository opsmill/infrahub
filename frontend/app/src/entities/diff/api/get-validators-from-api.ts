import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_VALIDATORS = graphql(`
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
`);

interface getValidatorsFromApiParams extends VariablesOf<typeof GET_VALIDATORS> {}

export const getValidatorsFromApi = async (variables: getValidatorsFromApiParams) => {
  return graphqlClient.query({ query: GET_VALIDATORS, variables });
};
