import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const GET_VALIDATOR_DETAILS = graphql(`
  query GET_VALIDATOR_DETAILS($ids: [ID!], $checksOffset: Int, $checksLimit: Int) {
    CoreValidator(ids: $ids) {
      edges {
        node {
          id
          checks(offset: $checksOffset, limit: $checksLimit, failed_first: true) {
            count
            edges {
              node {
                id
              }
            }
          }
        }
      }
    }
  }
`);

export interface GetValidatorDetailsFromApiParams
  extends VariablesOf<typeof GET_VALIDATOR_DETAILS> {}

export function getValidatorDetailsFromApi(variables: GetValidatorDetailsFromApiParams) {
  return graphqlClient.query({
    query: GET_VALIDATOR_DETAILS,
    variables,
  });
}
