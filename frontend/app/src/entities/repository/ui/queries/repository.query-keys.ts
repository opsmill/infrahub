import type { GetRepositoryBranchStatusParams } from "@/entities/repository/domain/use-cases/get-repository-branch-status";

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  branchStatus: (params: GetRepositoryBranchStatusParams) =>
    [...repositoryQueryKeys.all, "branch-status", params] as const,
};
