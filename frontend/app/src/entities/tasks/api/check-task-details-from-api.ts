import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const TASK_DETAILS_CHECK = graphql(`
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

export interface CheckTaskDetailsFromApiParams extends VariablesOf<typeof TASK_DETAILS_CHECK> {}

export function checkTaskDetailsFromApi(variables: CheckTaskDetailsFromApiParams) {
  return graphqlClient.query({
    query: TASK_DETAILS_CHECK,
    variables,
  });
}
