import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const RETRY_TASK = graphql(`
  mutation RETRY_TASK($id: String!) {
    InfrahubTaskRetry(data: { id: $id }) {
      ok
      task {
        id
      }
    }
  }
`);

export type RetryTaskFromApiParams = VariablesOf<typeof RETRY_TASK>;

export const retryTaskFromApi = async ({ id }: RetryTaskFromApiParams) => {
  return graphqlClient.mutate({
    mutation: RETRY_TASK,
    variables: { id },
  });
};
