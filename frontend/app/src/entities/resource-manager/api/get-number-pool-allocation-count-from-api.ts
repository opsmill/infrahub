import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import { BACKEND_MOCK_NUMBER_POOL_ID } from "@/entities/resource-manager/domain/model/number-pool";

const GET_NUMBER_POOL_ALLOCATION_COUNT = graphql(`
  query GET_NUMBER_POOL_ALLOCATION_COUNT($poolId: String!, $rangeId: String) {
    InfrahubNumberPoolAllocations(pool_id: $poolId, range_id: $rangeId, limit: 0) {
      count
    }
  }
`);

export interface GetNumberPoolAllocationCountFromApiParams extends ContextParams {
  poolId: string;
  rangeId?: string;
}

export function getNumberPoolAllocationCountFromApi({
  rangeId,
  branchName,
  atDate,
}: GetNumberPoolAllocationCountFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATION_COUNT,
    variables: { poolId: BACKEND_MOCK_NUMBER_POOL_ID, rangeId },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
