import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

import type { TaskRequestOptions } from "@/entities/tasks/api/get-task-list-from-api";

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

export function checkTaskDetailsFromApi(
  variables: CheckTaskDetailsFromApiParams,
  { silenceErrors = false }: TaskRequestOptions = {}
) {
  return graphqlClient.query({
    query: TASK_DETAILS_CHECK,
    variables,
    context: silenceErrors ? { processErrorMessage: () => {} } : undefined,
  });
}
