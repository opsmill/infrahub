import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const ABANDON_DELIVERY = graphql(`
  mutation ABANDON_DELIVERY($repositoryId: String!, $queueVersion: Int!) {
    InfrahubRepositoryDeliveryAbandon(
      data: { id: $repositoryId, queue_version: $queueVersion }
    ) {
      ok
      task {
        id
      }
    }
  }
`);

export interface AbandonDeliveryFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof ABANDON_DELIVERY> {}

export const abandonDeliveryFromApi = async ({
  repositoryId,
  queueVersion,
  branchName,
}: AbandonDeliveryFromApiParams) => {
  return graphqlClient.mutate({
    mutation: ABANDON_DELIVERY,
    variables: {
      repositoryId,
      queueVersion,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
