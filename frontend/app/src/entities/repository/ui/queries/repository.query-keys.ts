import type { BranchRepositoryListKind } from "@/entities/repository/domain/model/branch-repository";

export const repositoryQueryKeys = {
  all: ["repositories"] as const,
  branch: ({ branchName, kind }: { branchName: string; kind: BranchRepositoryListKind }) =>
    [...repositoryQueryKeys.all, "branch", branchName, kind] as const,
  importError: ({ branchName, repositoryId }: { branchName: string; repositoryId: string }) =>
    [...repositoryQueryKeys.all, "import-error", branchName, repositoryId] as const,
};
