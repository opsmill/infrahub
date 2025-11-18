import { gql } from "@apollo/client";

import type {
  Get_Ipam_Tree_NodesQuery,
  Get_Ipam_Tree_NodesQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_IPAM_TREE_NODES = gql`
  query GET_IPAM_TREE_NODES(
    $isTopLevel: Boolean
    $parentIds: [ID!]
    $search: String
    $ipNamespaceIds: [ID!]
    $limit: Int
    $offset: Int
  ) {
    BuiltinIPPrefix(
      is_top_level__value: $isTopLevel
      parent__ids: $parentIds
      any__value: $search
      partial_match: true
      ip_namespace__ids: $ipNamespaceIds
      offset: $offset
      limit: $limit
    ) {
      edges {
        node {
          id
          display_label
          descendants {
            count
          }
        }
      }
    }
  }
`;

export interface GetIpamTreeNodesByParentFromApiParams extends PaginationParams, ContextParams {
  namespaceId: string;
  parentObjectId?: string | null;
  search?: string;
}

export function GetIpamTreeNodesByParentFromApi({
  namespaceId,
  parentObjectId,
  search,
  limit,
  offset,
  branchName,
  atDate,
}: GetIpamTreeNodesByParentFromApiParams) {
  return graphqlClient.query<Get_Ipam_Tree_NodesQuery, Get_Ipam_Tree_NodesQueryVariables>({
    query: GET_IPAM_TREE_NODES,
    variables: {
      ipNamespaceIds: [namespaceId],
      limit,
      offset,
      ...(search
        ? { search }
        : parentObjectId
          ? { parentIds: [parentObjectId] }
          : { isTopLevel: true }),
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
