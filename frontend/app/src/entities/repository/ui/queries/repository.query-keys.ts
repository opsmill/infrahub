export interface RepositoryCommitsKeyParams {
  repositoryId: string;
  branchName: string;
  limit: number;
}

export const repositoriesQueryKeys = {
  all: ["repositories"] as const,
  commits: (params: RepositoryCommitsKeyParams) =>
    [...repositoriesQueryKeys.all, "commits", params] as const,
} as const;
