export interface RepositoryCommitsKeyParams {
  repositoryId: string;
  branchName: string;
  limit?: number;
}

export const repositoryQueryKeys = {
  all: ["repository"] as const,
  commits: (params: RepositoryCommitsKeyParams) =>
    [...repositoryQueryKeys.all, "commits", params] as const,
} as const;
