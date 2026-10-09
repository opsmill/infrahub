import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import {
  getFakeNumberPoolAllocations,
  USE_FAKE_NUMBER_POOL_DATA,
} from "@/entities/resource-manager/api/fake-number-pool-from-api";

const GET_NUMBER_POOL_ALLOCATIONS = graphql(`
  query GET_NUMBER_POOL_ALLOCATIONS(
    $poolId: String!
    $rangeId: String
    $offset: Int!
    $limit: Int!
  ) {
    InfrahubNumberPoolAllocations(
      pool_id: $poolId
      range_id: $rangeId
      offset: $offset
      limit: $limit
    ) {
      allocations {
        value
        branch
        provenance
        holder {
          id
          kind
          display_label
        }
        range {
          id
        }
      }
    }
  }
`);

export type NumberPoolAllocationsResponse = ResultOf<typeof GET_NUMBER_POOL_ALLOCATIONS>;

export type NumberPoolAllocationsNode =
  NumberPoolAllocationsResponse["InfrahubNumberPoolAllocations"];

export type NumberPoolAllocationNode = NumberPoolAllocationsNode["allocations"][number];

export interface GetNumberPoolAllocationsFromApiParams extends ContextParams {
  poolId: string;
  rangeId?: string;
  offset: number;
  limit: number;
}

export function getNumberPoolAllocationsFromApi({
  poolId,
  rangeId,
  offset,
  limit,
  branchName,
  atDate,
}: GetNumberPoolAllocationsFromApiParams) {
  if (USE_FAKE_NUMBER_POOL_DATA) {
    return getFakeNumberPoolAllocations({ poolId, rangeId, offset, limit, branchName, atDate });
  }

  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATIONS,
    variables: { poolId, rangeId, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
