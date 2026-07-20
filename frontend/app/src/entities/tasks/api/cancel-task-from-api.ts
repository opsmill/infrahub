import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const CANCEL_TASK = graphql(`
  mutation CANCEL_TASK($id: String!) {
    InfrahubTaskCancel(data: { id: $id }) {
      ok
      task {
        id
      }
    }
  }
`);

export type CancelTaskFromApiParams = VariablesOf<typeof CANCEL_TASK>;

export const cancelTaskFromApi = async ({ id }: CancelTaskFromApiParams) => {
  return graphqlClient.mutate({
    mutation: CANCEL_TASK,
    // Errors are surfaced by the mutation's own onError handler, so opt out of
    // the global errorLink toast to avoid notifying twice for one failure.
    context: {
      processErrorMessage: () => {},
    },
    variables: { id },
  });
};
