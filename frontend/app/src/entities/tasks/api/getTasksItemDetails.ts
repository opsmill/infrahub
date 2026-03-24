import { graphql } from "gql.tada";

export const TASK_DETAILS = graphql(`
  query TASK_DETAILS($ids: [String], $branch: String, $workflow: [String], $relatedNodes: [String]) {
    InfrahubTask(ids: $ids, branch: $branch, workflow: $workflow, related_node__ids: $relatedNodes) {
      count
      edges {
        node {
          id
          title
          related_node
          related_nodes {
            id
            kind
          }
          state
          progress
          created_at
          updated_at
          logs {
            edges {
              node {
                id
                message
                severity
                timestamp
              }
            }
          }
        }
      }
    }
  }
`);
