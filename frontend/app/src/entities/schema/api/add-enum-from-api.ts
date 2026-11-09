import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

export const ENUM_ADD_MUTATION = graphql(`
  mutation EnumAdd($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumAdd(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`);

export interface AddEnumFromApiParams extends VariablesOf<typeof ENUM_ADD_MUTATION> {}

export function addEnumFromApi(variables: AddEnumFromApiParams) {
  return graphqlClient.mutate({
    mutation: ENUM_ADD_MUTATION,
    variables,
  });
}
