import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const RETRY_DELIVERY = graphql(`
  mutation RETRY_DELIVERY($repositoryId: String!) {
    InfrahubRepositoryDeliveryRetry(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface RetryDeliveryFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof RETRY_DELIVERY> {}

export const retryDeliveryFromApi = async ({
  repositoryId,
  branchName,
}: RetryDeliveryFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RETRY_DELIVERY,
    variables: {
      repositoryId,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
