import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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

export type ReimportLastCommitFromApiParams = VariablesOf<typeof REIMPORT_LAST_COMMIT>;

export const reimportLastCommitFromApi = async ({
  repositoryId,
}: ReimportLastCommitFromApiParams) => {
  return graphqlClient.mutate({
    mutation: REIMPORT_LAST_COMMIT,
    variables: {
      repositoryId,
    },
  });
};
