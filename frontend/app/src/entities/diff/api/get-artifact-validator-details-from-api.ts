import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const GET_ARTIFACT_VALIDATOR_DETAILS = graphql(`
  query GET_ARTIFACT_VALIDATOR_DETAILS(
    $ids: [ID!]
    $checksOffset: Int
    $checksLimit: Int
    $checksFailedFirst: Boolean!
  ) {
    CoreArtifactValidator(ids: $ids) {
      edges {
        node {
          id
          checks(offset: $checksOffset, limit: $checksLimit, failed_first: $checksFailedFirst) {
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

export type GetArtifactValidatorDetailsFromApiParams = VariablesOf<
  typeof GET_ARTIFACT_VALIDATOR_DETAILS
>;

export function getArtifactValidatorDetailsFromApi(
  variables: GetArtifactValidatorDetailsFromApiParams
) {
  return graphqlClient.query({ query: GET_ARTIFACT_VALIDATOR_DETAILS, variables });
}
