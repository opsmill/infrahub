import { queryOptions, replaceEqualDeep, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { RepositoryCommitStatus } from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";
import { shouldPollGitState } from "@/entities/repository/domain/rules/should-poll-git-state";
import {
  type GetRepositoryCommitStatusParams,
  getRepositoryCommitStatus,
} from "@/entities/repository/domain/use-cases/get-repository-commit-status";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export const REPOSITORY_COMMITS_POLL_INTERVAL_MS = 10_000;

export function keepStatusOverColdAnswer(
  previous: RepositoryCommitStatus | undefined,
  next: RepositoryCommitStatus
): RepositoryCommitStatus {
  return previous && isGitStateAvailable(previous) && !isGitStateAvailable(next)
    ? previous
    : replaceEqualDeep(previous, next);
}

export function getRepositoryCommitStatusQueryOptions(params: GetRepositoryCommitStatusParams) {
  return queryOptions({
    queryKey: repositoriesQueryKeys.commitStatus({
      repositoryId: params.repositoryId,
      branchName: params.branchName,
    }),
    queryFn: () => getRepositoryCommitStatus(params),
    refetchInterval: (query) => {
      const status = query.state.data;
      return status && shouldPollGitState(status) ? REPOSITORY_COMMITS_POLL_INTERVAL_MS : false;
    },
    refetchOnWindowFocus: false,
    // TanStack types structuralSharing's arguments as unknown.
    structuralSharing: (oldData, newData) =>
      keepStatusOverColdAnswer(
        oldData as RepositoryCommitStatus | undefined,
        newData as RepositoryCommitStatus
      ),
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
