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
    variables: { id },
  });
};
