import type { GetBranchRepositoriesParams } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import type { GetBranchRepositoryHealthParams } from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import type { GetImportTaskErrorMessageParams } from "@/entities/repository/domain/use-cases/get-import-task-error-message";
import type { GetLatestRepositoryImportTaskParams } from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";
import type { GetRepositoryBranchStatusParams } from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import type { GetRepositoryNamesParams } from "@/entities/repository/domain/use-cases/get-repository-names";

export interface RepositoryKeyParams {
  repositoryId: string;
  branchName: string;
}

export interface RepositoryCommitsKeyParams extends RepositoryKeyParams {
  limit: number;
}

export interface RemoteCheckTaskKeyParams {
  taskId: string;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  repository: ({ repositoryId, branchName }: RepositoryKeyParams) =>
    [...repositoriesQueryKeys.all, { repositoryId, branchName }] as const,
  commits: ({ limit, ...params }: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.repository(params), "commits", { limit }] as const,
  // Outside `repository`: the commit-log refetch this task triggers when it ends must not refetch it.
  remoteCheckTask: ({ taskId }: RemoteCheckTaskKeyParams) =>
    [...repositoriesQueryKeys.all, "remote-check-task", { taskId }] as const,
} as const;

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  syncHealth: (branch: string) => [...repositoryQueryKeys.all, "sync-health", branch] as const,
  branchRepositoryList: (params: Pick<GetBranchRepositoriesParams, "branchName" | "syncWithGit">) =>
    [...repositoryQueryKeys.all, "branch-repositories", params] as const,
  branchRepositories: (params: GetBranchRepositoriesParams) =>
    [...repositoryQueryKeys.all, "branch-repositories", params] as const,
  branchHealth: (params: GetBranchRepositoryHealthParams) =>
    [...repositoryQueryKeys.all, "branch-health", params] as const,
  latestImportTask: (params: GetLatestRepositoryImportTaskParams) =>
    [...repositoryQueryKeys.all, "latest-import-task", params] as const,
  importLog: (params: Pick<GetImportTaskErrorMessageParams, "taskId">) =>
    [...repositoryQueryKeys.all, "import-log", params] as const,
  namesOnBranch: (params: Pick<GetRepositoryNamesParams, "branchName">) =>
    [...repositoryQueryKeys.all, "names", params] as const,
  names: (params: GetRepositoryNamesParams) =>
    [...repositoryQueryKeys.all, "names", params] as const,
  branchStatus: (params: GetRepositoryBranchStatusParams) =>
    [...repositoryQueryKeys.all, "branch-status", params] as const,
};
