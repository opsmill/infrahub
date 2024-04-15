import { gql } from "@apollo/client";

export const GET_IP_ADDRESS = gql`
  query IpamIPAddress($ids: [String!]) {
    IpamIPAddress(ip_prefix__ids: $ids) {
      edges {
        node {
          display_label
          ip_namespace {
            node {
              id
            }
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
          description {
            id
          }
          id
        }
      }
    }
  }
`;
