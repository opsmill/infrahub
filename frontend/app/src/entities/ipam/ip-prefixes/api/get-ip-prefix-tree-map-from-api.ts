import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

export const GET_IP_PREFIX_TREE_MAP = graphql(`
  query GET_IP_PREFIX_TREE_MAP($parentId: ID!, $parentIds: [ID!], $limit: Int) {
    parent: BuiltinIPPrefix(ids: [$parentId]) {
      edges {
        node {
          __typename
          id
          prefix {
            value
            prefixlen
            version
          }
          member_type {
            value
          }
          utilization {
            value
          }
        }
      }
    }
    BuiltinIPPrefix(parent__ids: $parentIds, include_available: true, limit: $limit) {
      count
      edges {
        node {
          __typename
          id
          prefix {
            value
            prefixlen
            version
          }
          member_type {
            value
          }
          utilization {
            value
          }
          is_pool {
            value
          }
          description {
            value
          }
          children {
            count
          }
          ip_addresses {
            count
          }
        }
      }
    }
  }
`);

export interface GetIpPrefixTreeMapFromApiParams extends ContextParams {
  parentId: string;
  limit: number;
}

export function getIpPrefixTreeMapFromApi({
  parentId,
  limit,
  branchName,
  atDate,
}: GetIpPrefixTreeMapFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_PREFIX_TREE_MAP,
    variables: { parentId, parentIds: [parentId], limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
