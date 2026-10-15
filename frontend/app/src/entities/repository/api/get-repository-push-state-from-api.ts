import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_PUSH_STATE = graphql(`
  query REPOSITORY_PUSH_STATE($repositoryId: ID!) {
    CoreRepository(ids: [$repositoryId]) {
      edges {
        node {
          id
          delivery_status {
            value
            label
            color
          }
          delivery_failure_cause {
            value
            label
          }
          delivery_error {
            value
          }
          delivery_queue {
            value
          }
        }
      }
    }
  }
`);

export interface GetRepositoryPushStateFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_PUSH_STATE> {}

export const getRepositoryPushStateFromApi = async ({
  repositoryId,
  branchName,
}: GetRepositoryPushStateFromApiParams) => {
  return graphqlClient.query({
    query: REPOSITORY_PUSH_STATE,
    variables: {
      repositoryId,
    },
    context: { branch: branchName },
  });
};
