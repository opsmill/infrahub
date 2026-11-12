import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const ABANDON_REPOSITORY_PUSH = graphql(`
  mutation ABANDON_REPOSITORY_PUSH($repositoryId: String!, $queueVersion: Int!) {
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

export interface AbandonRepositoryPushFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof ABANDON_REPOSITORY_PUSH> {}

export const abandonRepositoryPushFromApi = async ({
  repositoryId,
  queueVersion,
  branchName,
}: AbandonRepositoryPushFromApiParams) => {
  return graphqlClient.mutate({
    mutation: ABANDON_REPOSITORY_PUSH,
    variables: {
      repositoryId,
      queueVersion,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
