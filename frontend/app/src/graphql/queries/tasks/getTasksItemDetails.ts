import { gql } from "@apollo/client";

export const TASK_DETAILS = gql`
query TASK_DETAILS($ids: [String], $relatedNodes: [String]) {
  InfrahubTask(ids: $ids, related_node__ids: $relatedNodes) {
    count
    edges {
      node {
        id
        title
        related_node_kind
        related_node
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
`;
