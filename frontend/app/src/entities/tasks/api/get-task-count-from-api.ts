import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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

export function getTaskCountFromApi(variables?: GetTaskCountFromApiParams) {
  return graphqlClient.query({
    query: TASK_COUNT,
    variables,
  });
}
