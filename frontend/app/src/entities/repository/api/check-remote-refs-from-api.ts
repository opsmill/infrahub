import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const CHECK_REMOTE_REFS = graphql(`
  mutation CHECK_REMOTE_REFS($repositoryId: String!) {
    InfrahubReadOnlyRepositoryCheckRefs(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface CheckRemoteRefsFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof CHECK_REMOTE_REFS> {}

export const checkRemoteRefsFromApi = async ({
  repositoryId,
  branchName,
}: CheckRemoteRefsFromApiParams) => {
  return graphqlClient.mutate({
    mutation: CHECK_REMOTE_REFS,
    variables: {
      repositoryId,
    },
    // The caller shows the error toast, so the client's own toast would show it twice.
    context: { branch: branchName, processErrorMessage: () => {} },
  });
};
