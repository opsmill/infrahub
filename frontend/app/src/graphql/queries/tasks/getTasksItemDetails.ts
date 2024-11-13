import { gql } from "@apollo/client";

export const TASK_DETAILS = gql`
query TASK_DETAILS($ids: [String], $branch: String, $workflow: [String]) {
  InfrahubTask(ids: $ids, branch: $branch, workflow: $workflow) {
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
