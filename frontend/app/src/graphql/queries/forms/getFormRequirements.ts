import { gql } from "@apollo/client";

export const GET_FORM_REQUIREMENTS = gql`
  query GET_FORM_REQUIREMENTS($kind: String!) {
    CoreNumberPool(node__value: $kind) {
      edges {
        node {
          id
          display_label
          name {
            id
            value
          }
          node {
            id
            value
          }
          node_attribute {
            id
            value
          }
        }
      }
    }
  }
`;
