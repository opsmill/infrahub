import { ERROR_CODES } from "@/shared/api/errors";
import { hasThrownCatalogueCode } from "@/shared/api/graphql/error-handling";

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

function toRepositoryBranchStatusError(error: unknown): RepositoryBranchStatusError {
  const code = hasThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)
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
