import { graphql } from "gql.tada";

export const TASK_DETAILS_CHECK = graphql(`
  query TASK_DETAILS_CHECK(
    $ids: [String]
    $branch: String
    $workflow: [String]
    $state: [StateType]
    $relatedNodes: [String]
  ) {
    InfrahubTask(
      ids: $ids
      branch: $branch
      workflow: $workflow
      state: $state
      related_node__ids: $relatedNodes
    ) {
      count
    }
  }
`);
