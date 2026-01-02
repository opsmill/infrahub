import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_TASKS_HOMEPAGE = graphql(`
  query GET_TASKS_HOMEPAGE($limit: Int, $branchName: String!, $states: [StateType]) {
    InfrahubTask(limit: $limit, branch: $branchName, state: $states) {
      count
      edges {
        node {
          id
          branch
          title
          updated_at
          state
          related_nodes {
            id
            kind
          }
        }
      }
    }
  }
`);

export interface GetTasksHomepageFromApiParams extends VariablesOf<typeof GET_TASKS_HOMEPAGE> {}

export const getTasksHomepageFromApi = (params: GetTasksHomepageFromApiParams) => {
  return graphqlClient.query({
    query: GET_TASKS_HOMEPAGE,
    variables: params,
  });
};
