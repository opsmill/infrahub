import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const RETRY_PUSH = graphql(`
  mutation RETRY_PUSH($repositoryId: String!) {
    InfrahubRepositoryDeliveryRetry(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface RetryPushFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof RETRY_PUSH> {}

export const retryPushFromApi = async ({ repositoryId, branchName }: RetryPushFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RETRY_PUSH,
    variables: {
      repositoryId,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
