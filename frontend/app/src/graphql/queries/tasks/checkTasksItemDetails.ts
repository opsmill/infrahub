import { gql } from "@apollo/client";

export const TASK_DETAILS_CHECK = gql`
query TASK_DETAILS_CHECK($ids: [String], $branch: String, $workflow: [String], $relatedNodes: [String]) {
  InfrahubTask(ids: $ids, branch: $branch, workflow: $workflow, related_node__ids: $relatedNodes) {
    count
  }
}
`;
