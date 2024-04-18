import { gql } from "@apollo/client";

export const GET_PREFIXES_ONLY = gql`
  query GET_PREFIXES($parentIds: [ID!]) {
    IpamIPPrefix(parent__ids: $parentIds) {
      edges {
        node {
          id
          display_label
          parent {
            node {
              id
            }
          }
          children {
            count
          }
        }
      }
    }
  }
`;

export const GET_PREFIXES = gql`
  query IpamIPPrefix($namespace: String, $prefix: String, $offset: Int, $limit: Int) {
    IpamIPPrefix(
      ip_namespace__name__value: $namespace
      prefix__value: $prefix
      offset: $offset
      limit: $limit
    ) {
      count
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
            count
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
