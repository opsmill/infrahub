import {
  graphql,
  graphqlClient,
  type ResultOf,
  type VariablesOf,
} from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_POOL_ALLOCATIONS = graphql(`
  query GET_IP_POOL_ALLOCATIONS(
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
          identifier
        }
      }
    }
  }
`);

export type IpPoolAllocationsNode = ResultOf<
  typeof GET_IP_POOL_ALLOCATIONS
>["InfrahubResourcePoolAllocated"];

export interface GetIpPoolAllocationsFromApiParams
  extends ContextParams,
    VariablesOf<typeof GET_IP_POOL_ALLOCATIONS> {}

export function getIpPoolAllocationsFromApi({
  poolId,
  resourceId,
  limit,
  offset,
  branchName,
  atDate,
}: GetIpPoolAllocationsFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_POOL_ALLOCATIONS,
    variables: { poolId, resourceId, limit, offset },
    context: { branch: branchName, date: atDate },
  });
}
