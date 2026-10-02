import { CombinedError } from "@urql/core";

import { ERROR_CODES, parseCatalogueError } from "@/shared/api/errors";
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

// The transport throws a bare `Error` carrying the GraphQL errors on `.cause`. Denied only when
// every one of them is a permission denial, so any other failure still reads as a failure.
function isPermissionDenied(error: unknown): boolean {
  const combined = error instanceof CombinedError || !(error instanceof Error) ? error : error.cause;
  const graphQLErrors = combined instanceof CombinedError ? combined.graphQLErrors : [];

  return (
    graphQLErrors.length > 0 &&
    graphQLErrors.every(
      ({ extensions }) => parseCatalogueError(extensions).code === ERROR_CODES.PERMISSION_DENIED
    )
  );
}

// A missing object permission rejects the whole query rather than dropping rows from it.
function toBranchRepositoriesError(error: unknown): BranchRepositoriesError {
  const code = isPermissionDenied(error) ? "PERMISSION_DENIED" : "UNKNOWN";
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
