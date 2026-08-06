import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const CHECK_REPOSITORY_CONNECTIVITY = graphql(`
  mutation CHECK_REPOSITORY_CONNECTIVITY($repositoryId: String!) {
    InfrahubRepositoryConnectivity(data: { id: $repositoryId }) {
      ok
      message
    }
  }
`);

export type CheckConnectivityFromApiParams = VariablesOf<typeof CHECK_REPOSITORY_CONNECTIVITY>;

export const checkConnectivityFromApi = async ({
  repositoryId,
}: CheckConnectivityFromApiParams) => {
  return graphqlClient.mutate({
    mutation: CHECK_REPOSITORY_CONNECTIVITY,
    variables: {
      repositoryId,
    },
  });
};
