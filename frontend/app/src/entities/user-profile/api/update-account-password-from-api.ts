import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPDATE_ACCOUNT_PASSWORD = graphql(`
  mutation UPDATE_ACCOUNT_PASSWORD($password: String!) {
    InfrahubAccountSelfUpdate(data: { password: $password }) {
      ok
    }
  }
`);

export interface UpdateAccountPasswordFromApiParams
  extends VariablesOf<typeof UPDATE_ACCOUNT_PASSWORD> {}

export function updateAccountPasswordFromApi(variables: UpdateAccountPasswordFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPDATE_ACCOUNT_PASSWORD,
    variables,
  });
}
