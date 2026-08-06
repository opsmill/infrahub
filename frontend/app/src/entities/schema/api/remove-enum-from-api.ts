import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

export const ENUM_REMOVE_MUTATION = graphql(`
  mutation EnumDelete($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumRemove(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`);

export interface RemoveEnumFromApiParams extends VariablesOf<typeof ENUM_REMOVE_MUTATION> {}

export function removeEnumFromApi(variables: RemoveEnumFromApiParams) {
  return graphqlClient.mutate({
    mutation: ENUM_REMOVE_MUTATION,
    variables,
  });
}
