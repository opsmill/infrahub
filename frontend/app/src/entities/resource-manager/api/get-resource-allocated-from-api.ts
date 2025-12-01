import { gql } from "@apollo/client";

import type {
  Get_Resource_Pool_AllocatedQuery,
  Get_Resource_Pool_AllocatedQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

export const GET_RESOURCE_ALLOCATED = gql`
  query GET_RESOURCE_POOL_ALLOCATED(
    $poolId: String!
    $resourceId: String!
    $limit: Int
    $offset: Int
  ) {
    InfrahubResourcePoolAllocated(
      pool_id: $poolId
      resource_id: $resourceId
      limit: $limit
      offset: $offset
    ) {
      count
      edges {
        node {
          id
          display_label
          kind
          branch
          identifier
        }
      }
    }
  }
`;

export interface GetResourceAllocatedFromApiParams extends PaginationParams {
  poolId: string;
  resourceId: string;
}

export function getResourceAllocatedFromApi({
  poolId,
  resourceId,
  limit,
  offset,
}: GetResourceAllocatedFromApiParams) {
  return graphqlClient.query<
    Get_Resource_Pool_AllocatedQuery,
    Get_Resource_Pool_AllocatedQueryVariables
  >({
    query: GET_RESOURCE_ALLOCATED,
    variables: {
      poolId,
      resourceId,
      limit,
      offset,
    },
  });
}
