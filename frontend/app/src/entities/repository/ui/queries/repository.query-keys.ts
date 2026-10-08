export interface RepositoryKeyParams {
  repositoryId: string;
  branchName: string;
}

export interface RepositoryCommitsKeyParams extends RepositoryKeyParams {
  limit: number;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  repository: ({ repositoryId, branchName }: RepositoryKeyParams) =>
    [...repositoriesQueryKeys.all, { repositoryId, branchName }] as const,
  commits: ({ limit, ...params }: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.repository(params), "commits", { limit }] as const,
} as const;
