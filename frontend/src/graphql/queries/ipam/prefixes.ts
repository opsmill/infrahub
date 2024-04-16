import { gql } from "@apollo/client";

export const GET_PREFIXES = gql`
  query IpamIPPrefix($namespace: String, $prefix: String) {
    IpamIPPrefix(ip_namespace__name__value: $namespace, prefix__value: $prefix) {
      edges {
        node {
          display_label
          id
          prefix {
            id
            value
          }
          parent {
            node {
              id
              display_label
              prefix {
                value
              }
            }
          }
          children {
            edges {
              node {
                id
                display_label
                prefix {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`;
