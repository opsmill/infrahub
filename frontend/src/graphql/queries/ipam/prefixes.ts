import { gql } from "@apollo/client";

export const GET_PREFIXES_ONLY = gql`
  query GET_PREFIXES_ONLY($parentIds: [ID!]) {
    BuiltinIPPrefix(parent__ids: $parentIds) {
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
  query GET_PREFIXES($namespace: String, $prefix: String, $offset: Int, $limit: Int) {
    BuiltinIPPrefix(
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
  query GET_PREFIX($namespace: String, $ids: [ID], $offset: Int, $limit: Int) {
    BuiltinIPPrefix(ip_namespace__name__value: $namespace, ids: $ids) {
      count
      edges {
        node {
          display_label
          parent {
            node {
              id
              display_label
              prefix {
                value
              }
            }
          }
          children(offset: $offset, limit: $limit) {
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

export const GET_PREFIX_KIND = gql`
  query GET_PREFIX_KIND($ids: [ID]) {
    BuiltinIPPrefix(ids: $ids) {
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

export const GET_TOP_LEVEL_PREFIXES = gql`
  query GET_TOP_LEVEL_PREFIXES {
    BuiltinIPPrefix(is_top_level__value: true) {
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

export const GET_PREFIX_ANCESTORS = gql`
  query GET_PREFIX_ANCESTORS($ids: [ID]) {
    BuiltinIPPrefix(ids: $ids) {
      edges {
        node {
          id
          display_label
          ancestors {
            edges {
              node {
                id
                display_label
                parent {
                  node {
                    id
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
