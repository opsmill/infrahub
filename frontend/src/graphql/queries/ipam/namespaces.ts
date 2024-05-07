import { gql } from "@apollo/client";

export const GET_NAMESPACES = gql`
  query BuiltinIPNamespace {
    BuiltinIPNamespace {
      edges {
        node {
          display_label
          id
          name {
            id
          }
          description {
            id
          }
          ... on IpamNamespace {
            default {
              value
            }
          }
        }
      }
    }
  }
`;
