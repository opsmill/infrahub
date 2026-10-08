import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { RangeInput } from "@/entities/resource-manager/domain/model/number-pool-range";

const CREATE_NUMBER_POOL_RANGE = graphql(`
  mutation CREATE_NUMBER_POOL_RANGE(
    $poolId: String!
    $start: BigInt!
    $end: BigInt!
    $weight: BigInt
  ) {
    CoreNumberPoolRangeCreate(
      data: {
        pool: { id: $poolId }
        start: { value: $start }
        end: { value: $end }
        allocation_weight: { value: $weight }
      }
    ) {
      ok
      object {
        id
      }
    }
  }
`);

export interface CreateNumberPoolRangeFromApiParams extends BranchContextParams {
  poolId: string;
  range: RangeInput;
}

export function createNumberPoolRangeFromApi({
  poolId,
  range,
  branchName,
}: CreateNumberPoolRangeFromApiParams) {
  return graphqlClient.mutate({
    mutation: CREATE_NUMBER_POOL_RANGE,
    variables: { poolId, start: range.start, end: range.end, weight: range.weight },
    // The form shows the refusal inline, so the global toast is suppressed to avoid a second message.
    context: {
      branch: branchName,
      processErrorMessage: () => {},
    },
  });
}
