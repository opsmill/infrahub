import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { DROPDOWN_ADD_MUTATION } from "@/entities/schema/api/dropdown";

export interface AddDropdownFromApiParams extends VariablesOf<typeof DROPDOWN_ADD_MUTATION> {}

export function addDropdownFromApi(variables: AddDropdownFromApiParams) {
  return graphqlClient.mutate({
    mutation: DROPDOWN_ADD_MUTATION,
    variables,
  });
}
