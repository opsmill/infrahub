import { toBranchGitRepositoryPage } from "@/entities/branch-git-status/api/branch-git-repository.mappers";
import {
  type GetBranchGitRepositoriesFromApiParams,
  getBranchGitRepositoriesFromApi,
} from "@/entities/branch-git-status/api/get-branch-git-repositories-from-api";
import type { BranchGitRepositoryPage } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import { toBranchGitStatusError } from "@/entities/branch-git-status/domain/rules/to-branch-git-status-error";

export type GetBranchGitRepositoriesParams = GetBranchGitRepositoriesFromApiParams;

export type GetBranchGitRepositoriesResult = BranchGitRepositoryPage;

export type GetBranchGitRepositories = (
  params: GetBranchGitRepositoriesParams
) => Promise<GetBranchGitRepositoriesResult>;

export const getBranchGitRepositories: GetBranchGitRepositories = async (params) => {
  const connection = await getBranchGitRepositoriesFromApi(params).catch((error: unknown) => {
    throw toBranchGitStatusError(error, "Failed to load the repositories");
  });

  return toBranchGitRepositoryPage(connection);
};
