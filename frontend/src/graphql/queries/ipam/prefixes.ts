import { gql } from "@apollo/client";

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
          id
          display_label
          prefix {
            id
            value
          }
          description {
            value
          }
          member_type {
            value
          }
          is_pool {
            value
          }
          is_top_level {
            value
          }
          utilization {
            value
          }
          netmask {
            value
          }
          hostmask {
            value
          }
          network_address {
            value
          }
          broadcast_address {
            value
          }
          ip_namespace {
            node {
              display_label
            }
          }
          parent {
            node {
              id
              display_label
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

export const GET_PREFIX = gql`
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
          children {
            count
            edges {
              node {
                id
                display_label
                prefix {
                  id
                  value
                }
                description {
                  value
                }
                member_type {
                  value
                }
                is_pool {
                  value
                }
                is_top_level {
                  value
                }
                utilization {
                  value
                }
                netmask {
                  value
                }
                hostmask {
                  value
                }
                network_address {
                  value
                }
                broadcast_address {
                  value
                }
                ip_namespace {
                  node {
                    display_label
                  }
                }
              }
            }
          }
        }
      }
    }
  }
`;
