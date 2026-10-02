export interface RepositoryCommitStatusKeyParams {
  repositoryId: string;
  branchName: string;
}

export interface RepositoryCommitsKeyParams extends RepositoryCommitStatusKeyParams {
  limit: number;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  commits: (params: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.all, "commits", params] as const,
  commitStatus: (params: RepositoryCommitStatusKeyParams) =>
    [...repositoriesQueryKeys.all, "commitStatus", params] as const,
} as const;
