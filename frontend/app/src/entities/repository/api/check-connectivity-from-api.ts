import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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
