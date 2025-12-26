import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

const GET_RESOURCE_ALLOCATED = graphql(`
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
`);

type QueryVariables = VariablesOf<typeof GET_RESOURCE_ALLOCATED>;

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
  return graphqlClient.query({
    query: GET_RESOURCE_ALLOCATED,
    variables: {
      poolId,
      resourceId,
      limit,
      offset,
    } satisfies QueryVariables,
  });
}
