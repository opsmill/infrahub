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
  // Outside `repository`: the commit-log invalidation this task triggers must not refetch the task.
  remoteCheckTask: ({ taskId }: RemoteCheckTaskKeyParams) =>
    [...repositoriesQueryKeys.all, "remote-check-task", { taskId }] as const,
} as const;
