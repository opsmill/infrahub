import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const DROPDOWN_ADD_MUTATION = graphql(`
  mutation DropdownAdd(
    $kind: String!
    $attribute: String!
    $dropdown: String!
    $label: String
    $color: String
    $description: String
  ) {
    SchemaDropdownAdd(
      data: {
        kind: $kind
        attribute: $attribute
        dropdown: $dropdown
        label: $label
        color: $color
        description: $description
      }
    ) {
      ok
      object {
        value
        label
        color
        description
      }
    }
  }
`);

export interface AddDropdownFromApiParams extends VariablesOf<typeof DROPDOWN_ADD_MUTATION> {}

export function addDropdownFromApi(variables: AddDropdownFromApiParams) {
  return graphqlClient.mutate({
    mutation: DROPDOWN_ADD_MUTATION,
    variables,
  });
}
