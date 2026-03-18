import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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

export type ImportCurrentCommitFromApiParams = VariablesOf<typeof IMPORT_CURRENT_COMMIT>;

export const importCurrentCommitFromApi = async ({
  repositoryId,
}: ImportCurrentCommitFromApiParams) => {
  return graphqlClient.mutate({
    mutation: IMPORT_CURRENT_COMMIT,
    variables: {
      repositoryId,
    },
  });
};
