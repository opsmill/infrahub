import { gql } from "@apollo/client";

export const ENUM_ADD_MUTATION = gql`
  mutation EnumAdd($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumAdd(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`;

export const ENUM_REMOVE_MUTATION = gql`
  mutation EnumDelete($kind: String!, $attribute: String!, $enum: String!) {
    SchemaEnumRemove(data: { kind: $kind, attribute: $attribute, enum: $enum }) {
      ok
    }
  }
`;
