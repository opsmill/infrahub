import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const IMPORT_CURRENT_COMMIT = graphql(`
  mutation IMPORT_CURRENT_COMMIT($repositoryId: String!) {
    InfrahubRepositoryProcess(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface ImportCurrentCommitFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof IMPORT_CURRENT_COMMIT> {}

export const importCurrentCommitFromApi = async ({
  repositoryId,
  branchName,
}: ImportCurrentCommitFromApiParams) => {
  return graphqlClient.mutate({
    mutation: IMPORT_CURRENT_COMMIT,
    variables: {
      repositoryId,
    },
    context: { branch: branchName },
  });
};
