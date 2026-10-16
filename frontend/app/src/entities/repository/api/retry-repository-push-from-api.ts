import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const RETRY_REPOSITORY_PUSH = graphql(`
  mutation RETRY_REPOSITORY_PUSH($repositoryId: String!) {
    InfrahubRepositoryDeliveryRetry(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface RetryRepositoryPushFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof RETRY_REPOSITORY_PUSH> {}

export const retryRepositoryPushFromApi = async ({
  repositoryId,
  branchName,
}: RetryRepositoryPushFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RETRY_REPOSITORY_PUSH,
    variables: {
      repositoryId,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
