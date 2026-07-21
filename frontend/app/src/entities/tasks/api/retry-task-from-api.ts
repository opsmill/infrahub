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
    // Errors are surfaced by the mutation's own onError handler, so opt out of
    // the global errorLink toast to avoid notifying twice for one failure.
    context: {
      processErrorMessage: () => {},
    },
    variables: { id },
  });
};
