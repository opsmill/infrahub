import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_TASK_DETAILS = graphql(`
  query GET_TASK_DETAILS(
    $ids: [String]
    $branch: String
    $workflow: [String]
    $relatedNodes: [String]
  ) {
    InfrahubTask(
      ids: $ids
      branch: $branch
      workflow: $workflow
      related_node__ids: $relatedNodes
    ) {
      count
      edges {
        node {
          id
          title
          related_node
          related_nodes {
            id
            kind
          }
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
`);

export interface GetTaskDetailsFromApiParams extends VariablesOf<typeof GET_TASK_DETAILS> {}

export function getTaskDetailsFromApi(variables?: GetTaskDetailsFromApiParams) {
  return graphqlClient.query({
    query: GET_TASK_DETAILS,
    variables,
  });
}
