import { CombinedError } from "@urql/core";

import { ERROR_CODES } from "@/shared/api/errors";
import { hasCatalogueCode } from "@/shared/api/graphql/error-handling";

import {
  type GetRepositoryBranchStatusFromApiParams,
  getRepositoryBranchStatusFromApi,
} from "@/entities/repository/api/get-repository-branch-status-from-api";
import {
  mapRepositoryBranchStatusPage,
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";

export type GetRepositoryBranchStatusParams = GetRepositoryBranchStatusFromApiParams;

// The transport rethrows a `CombinedError` as a bare `Error` with the detail on `.cause`, so a
// denial is only distinguishable from a network failure by unwrapping it here.
function findCombinedError(error: unknown): CombinedError | undefined {
  if (error instanceof CombinedError) return error;

  const cause = error instanceof Error ? error.cause : null;
  return cause instanceof CombinedError ? cause : undefined;
}

function toRepositoryBranchStatusError(error: unknown): RepositoryBranchStatusError {
  const code = hasCatalogueCode(findCombinedError(error), ERROR_CODES.PERMISSION_DENIED)
    ? "PERMISSION_DENIED"
    : "UNKNOWN";
  const message =
    error instanceof Error ? error.message : "Failed to load the repository branch status";

  return new RepositoryBranchStatusError(code, message, { cause: error });
}

export type GetRepositoryBranchStatus = (
  params: GetRepositoryBranchStatusParams
) => Promise<RepositoryBranchStatusPage>;

export const getRepositoryBranchStatus: GetRepositoryBranchStatus = async (params) => {
  const { data } = await getRepositoryBranchStatusFromApi(params).catch((error: unknown) => {
    throw toRepositoryBranchStatusError(error);
  });

  return mapRepositoryBranchStatusPage(data.InfrahubRepositoryBranchStatus);
};
