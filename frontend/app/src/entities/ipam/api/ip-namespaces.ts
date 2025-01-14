import { gql } from "@apollo/client";

export const GET_IP_NAMESPACES = gql`
  query BuiltinIPNamespace {
    BuiltinIPNamespace {
      edges {
        node {
          display_label
          id
          name {
            id
            value
          }
          description {
            id
            value
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
