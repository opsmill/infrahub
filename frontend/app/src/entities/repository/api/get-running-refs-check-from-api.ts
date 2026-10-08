import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const RUNNING_REFS_CHECK = graphql(`
  query RUNNING_REFS_CHECK($workflow: [String], $state: [StateType], $repositoryId: String!) {
    InfrahubTask(
      workflow: $workflow
      state: $state
      related_node__ids: [$repositoryId]
      limit: 1
    ) {
      edges {
        node {
          id
        }
      }
    }
  }
`);

export interface GetRunningRefsCheckFromApiParams extends VariablesOf<typeof RUNNING_REFS_CHECK> {}

export const getRunningRefsCheckFromApi = (variables: GetRunningRefsCheckFromApiParams) => {
  return graphqlClient.query({
    query: RUNNING_REFS_CHECK,
    variables,
    // A background poll: a failure keeps the last answer on screen instead of raising a toast.
    context: { processErrorMessage: () => {} },
  });
};
