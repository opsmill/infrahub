import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

import type { TaskRequestOptions } from "@/entities/tasks/api/get-task-list-from-api";

const TASK_COUNT = graphql(`
  query TASK_COUNT(
    $search: String
    $branchName: String
    $state: [StateType]
    $relatedNodeIds: [String]
  ) {
    InfrahubTask(
      q: $search
      branch: $branchName
      state: $state
      related_node__ids: $relatedNodeIds
    ) {
      count
    }
  }
`);

export interface GetTaskCountFromApiParams extends VariablesOf<typeof TASK_COUNT> {}

export function getTaskCountFromApi(
  variables?: GetTaskCountFromApiParams,
  { silenceErrors = false }: TaskRequestOptions = {}
) {
  return graphqlClient.query({
    query: TASK_COUNT,
    variables,
    context: silenceErrors ? { processErrorMessage: () => {} } : undefined,
  });
}
