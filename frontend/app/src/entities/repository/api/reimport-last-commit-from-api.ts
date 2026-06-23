import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const REIMPORT_LAST_COMMIT = graphql(`
  mutation REIMPORT_LAST_COMMIT($repositoryId: String!) {
    InfrahubReadOnlyRepositoryImportLastCommit(data: { id: $repositoryId }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface ReimportLastCommitFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REIMPORT_LAST_COMMIT> {}

export const reimportLastCommitFromApi = async ({
  repositoryId,
  branchName,
}: ReimportLastCommitFromApiParams) => {
  return graphqlClient.mutate({
    mutation: REIMPORT_LAST_COMMIT,
    variables: {
      repositoryId,
    },
    context: { branch: branchName },
  });
};
