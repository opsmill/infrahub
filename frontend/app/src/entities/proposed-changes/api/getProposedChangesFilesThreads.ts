import { graphql } from "gql.tada";

export const GET_FILE_THREADS = graphql(`
  query GET_FILE_THREADS($changeIds: [ID!]) {
    CoreFileThread(change__ids: $changeIds) {
      count
      edges {
        node {
          id
          display_label
          resolved {
            value
          }
          __typename
          file {
            value
          }
          commit {
            value
          }
          repository {
            node {
              id
            }
          }
          line_number {
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
