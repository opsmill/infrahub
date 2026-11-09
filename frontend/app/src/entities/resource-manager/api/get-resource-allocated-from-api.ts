import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const GET_RESOURCE_ALLOCATED = graphql(`
  query GET_RESOURCE_POOL_ALLOCATED(
    $poolId: String!
    $resourceId: String!
    $limit: Int!
    $offset: Int!
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

export interface GetResourceAllocatedFromApiParams
  extends VariablesOf<typeof GET_RESOURCE_ALLOCATED> {}

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
    },
  });
}
