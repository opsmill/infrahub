import type { BranchContextParams } from "@/shared/api/types";

import { toBranchRepositories } from "@/entities/repository/api/branch-repository.mappers";
import { getBranchRepositoriesFromApi } from "@/entities/repository/api/get-branch-repositories-from-api";
import type { BranchRepositoryPage } from "@/entities/repository/domain/model/branch-repository";
import { toBranchRepositoriesError } from "@/entities/repository/domain/rules/branch-repositories-error";
import { getRepositoryListKind } from "@/entities/repository/domain/rules/get-repository-list-kind";

export interface GetBranchRepositoriesParams extends BranchContextParams {
  syncWithGit: boolean;
  limit: number;
  offset: number;
}

export type GetBranchRepositories = (
  params: GetBranchRepositoriesParams
) => Promise<BranchRepositoryPage>;

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
