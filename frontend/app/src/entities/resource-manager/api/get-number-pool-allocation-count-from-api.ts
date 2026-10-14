import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import type {
  NumberPoolAllocationFilters,
  NumberPoolDivisionSelector,
} from "@/entities/resource-manager/domain/model/number-pool";

const GET_NUMBER_POOL_ALLOCATION_COUNT = graphql(`
  query GET_NUMBER_POOL_ALLOCATION_COUNT(
    $poolId: String!
    $rangeId: String
    $division: [NumberPoolDivisionEntryInput!]
    $branch: String
    $provenance: PoolRecordProvenance
  ) {
    InfrahubNumberPoolAllocations(
      pool_id: $poolId
      range_id: $rangeId
      division: $division
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
  division?: NumberPoolDivisionSelector;
}

export function getNumberPoolAllocationCountFromApi({
  poolId,
  rangeId,
  division,
  branch,
  provenance,
  branchName,
  atDate,
}: GetNumberPoolAllocationCountFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATION_COUNT,
    variables: { poolId, rangeId, division, branch, provenance },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
