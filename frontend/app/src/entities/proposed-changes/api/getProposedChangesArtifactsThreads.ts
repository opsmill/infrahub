import { graphql } from "gql.tada";

export const GET_ARTIFACT_THREADS = graphql(`
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
