import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import type { RangeUpdate } from "@/entities/resource-manager/domain/model/number-pool-range";

const UPDATE_NUMBER_POOL_RANGE = graphql(`
  mutation UPDATE_NUMBER_POOL_RANGE(
    $id: String!
    $start: BigInt!
    $end: BigInt!
    $weight: BigInt
  ) {
    CoreNumberPoolRangeUpdate(
      data: {
        id: $id
        start: { value: $start }
        end: { value: $end }
        allocation_weight: { value: $weight }
      }
    ) {
      ok
    }
  }
`);

export interface UpdateNumberPoolRangeFromApiParams extends BranchContextParams {
  range: RangeUpdate;
}

export function updateNumberPoolRangeFromApi({
  range,
  branchName,
}: UpdateNumberPoolRangeFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPDATE_NUMBER_POOL_RANGE,
    variables: { id: range.id, start: range.start, end: range.end, weight: range.weight },
    // The form shows the refusal inline, so the global toast is suppressed to avoid a second message.
    context: {
      branch: branchName,
      processErrorMessage: () => {},
    },
  });
}
