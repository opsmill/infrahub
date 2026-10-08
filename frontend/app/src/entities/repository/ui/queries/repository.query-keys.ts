export interface RepositoryKeyParams {
  repositoryId: string;
  branchName: string;
}

export interface RepositoryCommitsKeyParams extends RepositoryKeyParams {
  limit: number;
}

export interface RunningRefsCheckKeyParams {
  repositoryId: string;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  repository: ({ repositoryId, branchName }: RepositoryKeyParams) =>
    [...repositoriesQueryKeys.all, { repositoryId, branchName }] as const,
  commits: ({ limit, ...params }: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.repository(params), "commits", { limit }] as const,
  // Outside `repository`: the commit-log refetch this check triggers when it ends must not refetch it.
  runningRefsCheck: ({ repositoryId }: RunningRefsCheckKeyParams) =>
    [...repositoriesQueryKeys.all, "running-refs-check", { repositoryId }] as const,
} as const;
