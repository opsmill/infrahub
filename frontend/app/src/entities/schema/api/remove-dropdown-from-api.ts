import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const DROPDOWN_REMOVE_MUTATION = graphql(`
  mutation DropdownDelete($kind: String!, $attribute: String!, $dropdown: String!) {
    SchemaDropdownRemove(data: { kind: $kind, attribute: $attribute, dropdown: $dropdown }) {
      ok
    }
  }
`);

export interface RemoveDropdownFromApiParams extends VariablesOf<typeof DROPDOWN_REMOVE_MUTATION> {}

export function removeDropdownFromApi(variables: RemoveDropdownFromApiParams) {
  return graphqlClient.mutate({
    mutation: DROPDOWN_REMOVE_MUTATION,
    variables,
  });
}
