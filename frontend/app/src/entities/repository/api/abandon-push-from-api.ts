import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const ABANDON_PUSH = graphql(`
  mutation ABANDON_PUSH($repositoryId: String!, $queueVersion: Int!) {
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

export interface AbandonPushFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof ABANDON_PUSH> {}

export const abandonPushFromApi = async ({
  repositoryId,
  queueVersion,
  branchName,
}: AbandonPushFromApiParams) => {
  return graphqlClient.mutate({
    mutation: ABANDON_PUSH,
    variables: {
      repositoryId,
      queueVersion,
    },
    // The caller's error toast shows the refusal message, so the global toast would repeat it.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
