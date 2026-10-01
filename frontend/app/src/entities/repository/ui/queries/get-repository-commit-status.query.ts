import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";
import {
  type GetRepositoryCommitStatusParams,
  getRepositoryCommitStatus,
} from "@/entities/repository/domain/use-cases/get-repository-commit-status";
import { REPOSITORY_COMMITS_POLL_INTERVAL_MS } from "@/entities/repository/ui/queries/get-repository-commits.query";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export function getRepositoryCommitStatusQueryOptions(params: GetRepositoryCommitStatusParams) {
  return queryOptions({
    queryKey: repositoriesQueryKeys.commitStatus({
      repositoryId: params.repositoryId,
      branchName: params.branchName,
    }),
    queryFn: () => getRepositoryCommitStatus(params),
    refetchInterval: (query) => {
      const status = query.state.data;
      return status && !isGitStateAvailable(status) ? REPOSITORY_COMMITS_POLL_INTERVAL_MS : false;
    },
    refetchOnWindowFocus: false,
  });
}

export type UseGetRepositoryCommitStatusConfig = QueryConfig<
  typeof getRepositoryCommitStatusQueryOptions
>;

export function useGetRepositoryCommitStatus(
  params: Omit<GetRepositoryCommitStatusParams, keyof ContextParams>,
  config: UseGetRepositoryCommitStatusConfig = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getRepositoryCommitStatusQueryOptions({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
