import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

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
