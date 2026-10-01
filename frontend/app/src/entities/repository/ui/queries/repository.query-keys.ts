import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";
import type { GetRepositoryBranchStatusParams } from "@/entities/repository/domain/use-cases/get-repository-branch-status";

export const repositoryQueryKeys = {
  all: ["repositories"] as const,
  branch: ({ branchName, kind }: { branchName: string; kind: BranchRepositoryListKind }) =>
    [...repositoryQueryKeys.all, "branch", branchName, kind] as const,
  branchStatus: (params: GetRepositoryBranchStatusParams) =>
    [...repositoryQueryKeys.all, "branch-status", params] as const,
  importError: ({ branchName, repositoryId }: { branchName: string; repositoryId: string }) =>
    [...repositoryQueryKeys.all, "import-error", branchName, repositoryId] as const,
};
