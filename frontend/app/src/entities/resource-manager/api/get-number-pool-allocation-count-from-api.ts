import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import {
  getFakeNumberPoolAllocationCount,
  USE_FAKE_NUMBER_POOL_DATA,
} from "@/entities/resource-manager/api/fake-number-pool-from-api";

const GET_NUMBER_POOL_ALLOCATION_COUNT = graphql(`
  query GET_NUMBER_POOL_ALLOCATION_COUNT($poolId: String!, $rangeId: String) {
    InfrahubNumberPoolAllocations(pool_id: $poolId, range_id: $rangeId, limit: 0) {
      count
    }
  }
`);

export type NumberPoolAllocationCountResponse = ResultOf<typeof GET_NUMBER_POOL_ALLOCATION_COUNT>;

export interface GetNumberPoolAllocationCountFromApiParams extends ContextParams {
  poolId: string;
  rangeId?: string;
}

export function getNumberPoolAllocationCountFromApi({
  poolId,
  rangeId,
  branchName,
  atDate,
}: GetNumberPoolAllocationCountFromApiParams) {
  if (USE_FAKE_NUMBER_POOL_DATA) {
    return getFakeNumberPoolAllocationCount({ poolId, rangeId, branchName, atDate });
  }

  return graphqlClient.query({
    query: GET_NUMBER_POOL_ALLOCATION_COUNT,
    variables: { poolId, rangeId },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
