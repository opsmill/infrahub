import { graphql } from "gql.tada";

export const ENUM_ADD_MUTATION = graphql(`
  mutation EnumAdd($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumAdd(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`);

export const ENUM_REMOVE_MUTATION = graphql(`
  mutation EnumDelete($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumRemove(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`);
