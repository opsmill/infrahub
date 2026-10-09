import { isGraphQLRequestError } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

import { createNumberPoolRangeFromApi } from "@/entities/resource-manager/api/create-number-pool-range-from-api";
import { deleteNumberPoolRangeFromApi } from "@/entities/resource-manager/api/delete-number-pool-range-from-api";
import { updateNumberPoolRangeFromApi } from "@/entities/resource-manager/api/update-number-pool-range-from-api";
import type { RangeChanges } from "@/entities/resource-manager/domain/model/number-pool-range";

export const UNEXPECTED_RANGE_SAVE_ERROR =
  "The ranges could not be saved because of an unexpected error. Try again.";

export interface ApplyNumberPoolRangeChangesParams extends BranchContextParams {
  poolId: string;
  changes: RangeChanges;
}

export interface ApplyNumberPoolRangeChangesResult {
  errorMessage: string | null;
}

export type ApplyNumberPoolRangeChanges = (
  params: ApplyNumberPoolRangeChangesParams
) => Promise<ApplyNumberPoolRangeChangesResult>;

function toErrorMessage(error: unknown): string {
  if (isGraphQLRequestError(error)) {
    return error.message;
  }

  return UNEXPECTED_RANGE_SAVE_ERROR;
}

/**
 * Sends deletes, then shrinking updates, then growing updates, then creates, so each call only takes
 * numbers that earlier calls have freed, and stops at the first rejection.
 */
export const applyNumberPoolRangeChanges: ApplyNumberPoolRangeChanges = async ({
  branchName,
  poolId,
  changes,
}) => {
  const calls: Array<() => Promise<unknown>> = [
    ...changes.deletes.map((id) => () => deleteNumberPoolRangeFromApi({ branchName, id })),
    ...[...changes.shrinks, ...changes.grows].map(
      (range) => () => updateNumberPoolRangeFromApi({ branchName, range })
    ),
    ...changes.creates.map(
      (range) => () => createNumberPoolRangeFromApi({ branchName, poolId, range })
    ),
  ];

  for (const call of calls) {
    try {
      await call();
    } catch (error) {
      return { errorMessage: toErrorMessage(error) };
    }
  }

  return { errorMessage: null };
};
