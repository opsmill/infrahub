import { gql } from "@apollo/client";

export const DROPDOWN_ADD_MUTATION = gql`
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
`;

export const DROPDOWN_REMOVE_MUTATION = gql`
  mutation DropdownDelete($kind: String!, $attribute: String!, $dropdown: String!) {
    SchemaDropdownRemove(data: { kind: $kind, attribute: $attribute, dropdown: $dropdown }) {
      ok
    }
  }
`;
