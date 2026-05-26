import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { DROPDOWN_REMOVE_MUTATION } from "@/entities/schema/api/dropdown";

export interface RemoveDropdownFromApiParams extends VariablesOf<typeof DROPDOWN_REMOVE_MUTATION> {}

export function removeDropdownFromApi(variables: RemoveDropdownFromApiParams) {
  return graphqlClient.mutate({
    mutation: DROPDOWN_REMOVE_MUTATION,
    variables,
  });
}
