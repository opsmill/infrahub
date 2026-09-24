import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const TASK_COUNT = graphql(`
  query TASK_COUNT(
    $search: String
    $branchName: String
    $state: [StateType]
    $workflow: [String]
    $workflowType: [WorkflowTypeEnum]
    $relatedNodeIds: [String]
  ) {
    InfrahubTask(
      q: $search
      branch: $branchName
      state: $state
      workflow: $workflow
      workflow_type: $workflowType
      related_node__ids: $relatedNodeIds
    ) {
      count
    }
  }
`);

export interface GetTaskCountFromApiParams extends VariablesOf<typeof TASK_COUNT> {}

export function getTaskCountFromApi(variables?: GetTaskCountFromApiParams) {
  return graphqlClient.query({
    query: TASK_COUNT,
    variables,
  });
}
