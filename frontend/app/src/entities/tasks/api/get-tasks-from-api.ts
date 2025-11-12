import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams, PaginationParams } from "@/shared/api/types";

export const GET_TASKS = gql`
query GET_TASKS(
  $offset: Int,
  $limit: Int,
  $search: String,
  $branch: String,
  $states: [StateType],
  $relatedNodes: [String]
) {
  InfrahubTask(
    offset: $offset
    limit: $limit
    q: $search
    branch: $branch
    state: $states
    related_node__ids: $relatedNodes
  ) {
    count
    edges {
      node {
        created_at
        id
        branch
        related_node
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
`;

export interface GetTasksFromApiParams extends PaginationParams, BranchContextParams {
  search?: string;
  states?: string[];
  relatedNodes?: string[];
}

export const getTasksFromApi = (params?: GetTasksFromApiParams) => {
  return graphqlClient.query({
    query: GET_TASKS,
    variables: params,
  });
};
