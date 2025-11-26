import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams, PaginationParams } from "@/shared/api/types";

export const GET_TASKS_HOMEPAGE = gql`
query GET_TASKS_HOMEPAGE(
  $limit: Int,
  $branchName: String,
  $states: [StateType],
) {
  InfrahubTask(
    limit: $limit
    branch: $branchName
    state: $states
  ) {
    count
    edges {
      node {
        id
        branch
        title
        updated_at
        state
      }
    }
  }
}
`;

export interface GetTasksHomepageFromApiParams
  extends Omit<PaginationParams, "offset">,
    BranchContextParams {
  states?: string[];
}

export const getTasksHomepageFromApi = (params: GetTasksHomepageFromApiParams) => {
  return graphqlClient.query({
    query: GET_TASKS_HOMEPAGE,
    variables: params,
  });
};
