import { ERROR_CODES } from "@/shared/api/errors";
import { hasThrownCatalogueCode } from "@/shared/api/graphql/error-handling";
import type { BranchContextParams } from "@/shared/api/types";

import { toBranchRepositories } from "@/entities/repository/api/branch-repository.mappers";
import { getBranchRepositoriesFromApi } from "@/entities/repository/api/get-branch-repositories-from-api";
import {
  BranchRepositoriesError,
  type BranchRepositoryPage,
} from "@/entities/repository/domain/model/branch-repository";
import { getRepositoryListKind } from "@/entities/repository/domain/rules/get-repository-list-kind";

export interface GetBranchRepositoriesParams extends BranchContextParams {
  syncWithGit: boolean;
  limit: number;
  offset: number;
}

export type GetBranchRepositories = (
  params: GetBranchRepositoriesParams
) => Promise<BranchRepositoryPage>;

// A missing object permission rejects the whole query rather than dropping rows from it.
function toBranchRepositoriesError(error: unknown): BranchRepositoriesError {
  const code = hasThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)
    ? "PERMISSION_DENIED"
    : "UNKNOWN";
  const message = error instanceof Error ? error.message : "Failed to load the repositories";

  return new BranchRepositoriesError(code, message, { cause: error });
}

export const getBranchRepositories: GetBranchRepositories = async ({
  branchName,
  syncWithGit,
  limit,
  offset,
}) => {
  const connection = await getBranchRepositoriesFromApi({
    branchName,
    kind: getRepositoryListKind(syncWithGit),
    limit,
    offset,
  }).catch((error: unknown) => {
    throw toBranchRepositoriesError(error);
  });

  return { repositories: toBranchRepositories(connection), count: connection.count };
};
