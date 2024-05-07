import { gql } from "@apollo/client";

export const GET_IP_ADDRESS_KIND = gql`
  query GET_IP_ADDRESS_KIND($ids: [ID]) {
    BuiltinIPAddress(ids: $ids) {
      edges {
        node {
          id
          display_label
          __typename
        }
      }
    }
  }
`;

export const GET_IP_ADDRESSES = gql`
  query GET_IP_ADDRESSES($prefixIds: [ID], $ipaddress: String, $offset: Int, $limit: Int) {
    BuiltinIPAddress(
      ip_prefix__ids: $prefixIds
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
