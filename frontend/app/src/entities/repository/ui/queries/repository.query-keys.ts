import type { GetBranchRepositoriesParams } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import type { GetBranchRepositoryHealthParams } from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import type { GetRepositoryImportTaskParams } from "@/entities/repository/domain/use-cases/get-repository-import-error";
import type { GetRepositoryNamesParams } from "@/entities/repository/domain/use-cases/get-repository-names";

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  syncHealth: (branch: string) => [...repositoryQueryKeys.all, "sync-health", branch] as const,
  branchRepositories: (params: GetBranchRepositoriesParams) =>
    [...repositoryQueryKeys.all, "branch-repositories", params] as const,
  branchHealth: (params: GetBranchRepositoryHealthParams) =>
    [...repositoryQueryKeys.all, "branch-health", params] as const,
  importTask: (params: GetRepositoryImportTaskParams) =>
    [...repositoryQueryKeys.all, "import-task", params] as const,
  importLog: (taskId: string) => [...repositoryQueryKeys.all, "import-log", taskId] as const,
  names: (params: GetRepositoryNamesParams) =>
    [...repositoryQueryKeys.all, "names", params] as const,
};
