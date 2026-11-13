import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const REMOTE_CHECK_TASK = graphql(`
  query REMOTE_CHECK_TASK($taskId: String!) {
    InfrahubTask(ids: [$taskId], limit: 1) {
      edges {
        node {
          state
        }
      }
    }
  }
`);

export interface GetRemoteCheckTaskFromApiParams extends VariablesOf<typeof REMOTE_CHECK_TASK> {}

export const getRemoteCheckTaskFromApi = (variables: GetRemoteCheckTaskFromApiParams) => {
  return graphqlClient.query({
    query: REMOTE_CHECK_TASK,
    variables,
    // A background poll: a failure keeps the last answer on screen instead of raising a toast.
    context: { processErrorMessage: () => {} },
  });
};
