import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import type { NumberPoolAllocationFilters } from "@/entities/resource-manager/domain/model/number-pool";

const GET_NUMBER_POOL_ALLOCATION_COUNT = graphql(`
  query GET_NUMBER_POOL_ALLOCATION_COUNT(
    $poolId: String!
    $rangeId: String
    $branch: String
    $provenance: PoolRecordProvenance
  ) {
    InfrahubNumberPoolAllocations(
      pool_id: $poolId
      range_id: $rangeId
      branch: $branch
      provenance: $provenance
      limit: 0
    ) {
      count
    }
  }
`);

export interface GetNumberPoolAllocationCountFromApiParams
  extends ContextParams,
    NumberPoolAllocationFilters {
  poolId: string;
  rangeId?: string;
}

export function getNumberPoolAllocationCountFromApi({
  poolId,
  rangeId,
  branch,
  provenance,
  branchName,
  atDate,
}: GetNumberPoolAllocationCountFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATION_COUNT,
    variables: { poolId, rangeId, branch, provenance },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
