import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { UPDATE_ACCOUNT_PASSWORD } from "@/entities/user-profile/api/updateAccountPassword";

export interface UpdateAccountPasswordFromApiParams
  extends VariablesOf<typeof UPDATE_ACCOUNT_PASSWORD> {}

export function updateAccountPasswordFromApi(variables: UpdateAccountPasswordFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPDATE_ACCOUNT_PASSWORD,
    variables,
  });
}
