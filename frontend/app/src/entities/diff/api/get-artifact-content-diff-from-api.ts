import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_ARTIFACT_THREADS = graphql(`
  query GET_ARTIFACT_THREADS($changeIds: [ID!]) {
    CoreArtifactThread(change__ids: $changeIds) {
      count
      edges {
        node {
          id
          display_label
          __typename
          line_number {
            value
          }
          storage_id {
            value
          }
          resolved {
            value
          }
          comments {
            edges {
              node_metadata {
                created_at
                created_by {
                  display_label
                }
              }
              node {
                id
                text {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);

export interface GetArtifactContentDiffFromApiParams {
  proposedChangeId: string;
}

export function getArtifactContentDiffFromApi(params: GetArtifactContentDiffFromApiParams) {
  return graphqlClient.query({
    query: GET_ARTIFACT_THREADS,
    variables: {
      changeIds: [params.proposedChangeId],
    },
    fetchPolicy: "no-cache",
  });
}
