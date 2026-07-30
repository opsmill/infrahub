import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

export const GET_TASK_LIST = graphql(`
  query GET_TASK_LIST(
    $offset: Int
    $limit: Int
    $search: String
    $branchName: String
    $state: [StateType]
    $relatedNodeIds: [String]
  ) {
    InfrahubTask(
      offset: $offset
      limit: $limit
      q: $search
      branch: $branchName
      state: $state
      related_node__ids: $relatedNodeIds
    ) {
      count
      edges {
        node {
          id
          branch
          related_nodes {
            id
            kind
          }
          title
          updated_at
          state
          progress
          workflow
        }
      }
    }
  }
`);

export interface GetTaskListFromApiParams extends VariablesOf<typeof GET_TASK_LIST> {}

export function getTaskListFromApi(variables?: GetTaskListFromApiParams) {
  return graphqlClient.query({
    query: GET_TASK_LIST,
    variables,
  });
}
