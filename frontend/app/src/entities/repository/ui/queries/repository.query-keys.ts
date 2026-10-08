import type { GetRepositoryBranchStatusParams } from "@/entities/repository/domain/use-cases/get-repository-branch-status";

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  syncHealth: (branch: string) => [...repositoryQueryKeys.all, "sync-health", branch] as const,
  branchStatus: (params: GetRepositoryBranchStatusParams) =>
    [...repositoryQueryKeys.all, "branch-status", params] as const,
};
