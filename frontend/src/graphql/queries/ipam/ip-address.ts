import { gql } from "@apollo/client";

export const GET_IP_ADDRESSES = gql`
  query IpamIPAddress($prefix: String, $ipaddress: String) {
    IpamIPAddress(ip_prefix__prefix__value: $prefix, address__value: $ipaddress) {
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
