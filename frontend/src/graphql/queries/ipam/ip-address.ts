import { gql } from "@apollo/client";

export const GET_IP_ADDRESS = gql`
  query IpamIPAddress($ids: [String!]) {
    IpamIPAddress(ip_prefix__ids: $ids) {
      edges {
        node {
          id
          display_label
          ip_namespace {
            node {
              id
              display_label
            }
          }
          ip_prefix {
            node {
              id
              display_label
            }
          }
          description {
            id
          }
          address {
            id
            value
            hostmask
            netmask
            prefixlen
            version
            with_hostmask
            with_netmask
          }
        }
      }
    }
  }
`;
