import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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
          created_at
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
