export interface RepositoryCommitStatusKeyParams {
  repositoryId: string;
  branchName: string;
}

export interface RepositoryCommitsKeyParams extends RepositoryCommitStatusKeyParams {
  limit: number;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  repository: ({ repositoryId, branchName }: RepositoryCommitStatusKeyParams) =>
    [...repositoriesQueryKeys.all, { repositoryId, branchName }] as const,
  commits: ({ limit, ...params }: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.repository(params), "commits", { limit }] as const,
  commitStatus: (params: RepositoryCommitStatusKeyParams) =>
    [...repositoriesQueryKeys.repository(params), "commitStatus"] as const,
} as const;
