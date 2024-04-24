import { gql } from "@apollo/client";

export const GET_IP_ADDRESS_KIND = gql`
  query GET_IP_ADDRESS_KIND($ip: String) {
    BuiltinIPAddress(address__value: $ip) {
      edges {
        node {
          __typename
        }
      }
    }
  }
`;

export const GET_IP_ADDRESSES = gql`
  query GET_IP_ADDRESSES($prefix: String, $ipaddress: String, $offset: Int, $limit: Int) {
    BuiltinIPAddress(
      ip_prefix__prefix__value: $prefix
      address__value: $ipaddress
      offset: $offset
      limit: $limit
    ) {
      count
      edges {
        node {
          id
          display_label
          ip_namespace {
            node {
              display_label
            }
          }
          ip_prefix {
            node {
              display_label
            }
          }
          description {
            value
          }
          address {
            value
          }
        }
      }
    }
  }
`;
