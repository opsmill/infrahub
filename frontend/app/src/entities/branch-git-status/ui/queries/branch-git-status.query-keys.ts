import type { GetBranchGitRepositoriesParams } from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";
import type { GetRepositoryBranchStatusParams } from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";

export const branchGitStatusQueryKeys = {
  all: ["branch-git-status"] as const,
  repositories: (params: GetBranchGitRepositoriesParams) =>
    [...branchGitStatusQueryKeys.all, "repositories", params] as const,
  repositoryBranchStatus: (params: GetRepositoryBranchStatusParams) =>
    [...branchGitStatusQueryKeys.all, "repository-branch-status", params] as const,
};
