import { gql } from "@apollo/client";

export const GET_PREFIXES_ONLY = gql`
  query GET_PREFIXES_ONLY($parentIds: [ID!], $search: String, $ipNamespaceIds: [ID!]) {
    BuiltinIPPrefix(parent__ids: $parentIds, any__value: $search, partial_match: true, ip_namespace__ids: $ipNamespaceIds) {
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
          descendants {
            count
          }
        }
      }
    }
  }
`;

export const GET_TOP_LEVEL_PREFIXES = gql`
  query GET_TOP_LEVEL_PREFIXES($namespaces: [ID]) {
    BuiltinIPPrefix(is_top_level__value: true, ip_namespace__ids: $namespaces) {
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
          descendants {
            count
          }
        }
      }
    }
  }
`;

export const GET_PREFIX_ANCESTORS = gql`
  query GET_PREFIX_ANCESTORS($ids: [ID], $namespaces: [ID]) {
    BuiltinIPPrefix(ids: $ids, ip_namespace__ids: $namespaces) {
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
