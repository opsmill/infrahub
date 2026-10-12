import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import type { NumberPoolAllocationFilters } from "@/entities/resource-manager/domain/model/number-pool";

const GET_NUMBER_POOL_ALLOCATIONS = graphql(`
  query GET_NUMBER_POOL_ALLOCATIONS(
    $poolId: String!
    $rangeId: String
    $offset: Int!
    $limit: Int!
    $branch: String
    $provenance: PoolRecordProvenance
  ) {
    InfrahubNumberPoolAllocations(
      pool_id: $poolId
      range_id: $rangeId
      branch: $branch
      provenance: $provenance
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

export interface GetNumberPoolAllocationsFromApiParams
  extends ContextParams,
    NumberPoolAllocationFilters {
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
  branch,
  provenance,
  branchName,
  atDate,
}: GetNumberPoolAllocationsFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATIONS,
    variables: { poolId, rangeId, offset, limit, branch, provenance },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
