import type { GetBranchRepositoriesParams } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import type { GetBranchRepositoryHealthParams } from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import type { GetImportTaskErrorMessageParams } from "@/entities/repository/domain/use-cases/get-import-task-error-message";
import type { GetLatestRepositoryImportTaskParams } from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";
import type { GetRepositoryNamesParams } from "@/entities/repository/domain/use-cases/get-repository-names";

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  syncHealth: (branch: string) => [...repositoryQueryKeys.all, "sync-health", branch] as const,
  branchRepositories: (params: GetBranchRepositoriesParams) =>
    [...repositoryQueryKeys.all, "branch-repositories", params] as const,
  branchHealth: (params: GetBranchRepositoryHealthParams) =>
    [...repositoryQueryKeys.all, "branch-health", params] as const,
  latestImportTask: (params: GetLatestRepositoryImportTaskParams) =>
    [...repositoryQueryKeys.all, "latest-import-task", params] as const,
  importLog: (params: GetImportTaskErrorMessageParams) =>
    [...repositoryQueryKeys.all, "import-log", params] as const,
  names: (params: GetRepositoryNamesParams) =>
    [...repositoryQueryKeys.all, "names", params] as const,
};
