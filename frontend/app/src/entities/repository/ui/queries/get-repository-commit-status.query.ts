import {
  type QueryClient,
  queryOptions,
  replaceEqualDeep,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { RepositoryCommitStatus } from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";
import { shouldPollGitState } from "@/entities/repository/domain/rules/should-poll-git-state";
import {
  type GetRepositoryCommitStatusParams,
  getRepositoryCommitStatus,
} from "@/entities/repository/domain/use-cases/get-repository-commit-status";
import {
  type RepositoryCommitStatusKeyParams,
  repositoriesQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_STALE_TIME_MS,
} from "@/entities/repository/ui/queries/repository-commits.constants";

export const REPOSITORY_COMMITS_POLL_INTERVAL_MS = 10_000;

export function keepStatusOverColdAnswer(
  previous: RepositoryCommitStatus | undefined,
  next: RepositoryCommitStatus
): RepositoryCommitStatus {
  return previous && isGitStateAvailable(previous) && !isGitStateAvailable(next)
    ? previous
    : replaceEqualDeep(previous, next);
}

// An open Commits tab writes the status from its log's first page, so its fetch and poll cover both
// — unless that log failed before loading anything.
function hasCommitLogFailedToLoad(
  client: QueryClient,
  { repositoryId, branchName }: RepositoryCommitStatusKeyParams
) {
  const commitLog = client.getQueryCache().find({
    queryKey: repositoriesQueryKeys.commits({
      repositoryId,
      branchName,
      limit: REPOSITORY_COMMITS_PAGE_SIZE,
    }),
  });
  return commitLog?.state.status === "error" && commitLog.state.data === undefined;
}

function getStatusPollInterval(status: RepositoryCommitStatus | undefined) {
  return status && shouldPollGitState(status) ? REPOSITORY_COMMITS_POLL_INTERVAL_MS : false;
}

export function getRepositoryCommitStatusQueryOptions(params: GetRepositoryCommitStatusParams) {
  return queryOptions({
    queryKey: repositoriesQueryKeys.commitStatus({
      repositoryId: params.repositoryId,
      branchName: params.branchName,
    }),
    queryFn: () => getRepositoryCommitStatus(params),
    refetchInterval: (query) => getStatusPollInterval(query.state.data),
    refetchOnWindowFocus: false,
    // The open Commits tab writes this status, so leaving the tab must not read it again at once.
    staleTime: REPOSITORY_COMMITS_STALE_TIME_MS,
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

export interface UseGetRepositoryCommitStatusParams
  extends Omit<GetRepositoryCommitStatusParams, keyof ContextParams> {
  isCommitLogOpen: boolean;
}

export function useGetRepositoryCommitStatus(
  { repositoryId, isCommitLogOpen }: UseGetRepositoryCommitStatusParams,
  config: UseGetRepositoryCommitStatusConfig = {}
) {
  const { currentBranch } = useCurrentBranch();
  const client = useQueryClient();
  const keyParams = { repositoryId, branchName: currentBranch.name };
  // An observer re-reads its options only on render or on its own query's updates, so a change in the commit log must re-render it.
  const hasLogFailed = useSyncExternalStore(
    (onChange) => client.getQueryCache().subscribe(onChange),
    () => hasCommitLogFailedToLoad(client, keyParams)
  );
  const isFedByCommitLog = isCommitLogOpen && !hasLogFailed;

  return useQuery({
    ...getRepositoryCommitStatusQueryOptions(keyParams),
    enabled: !isFedByCommitLog,
    refetchInterval: (query) =>
      isFedByCommitLog ? false : getStatusPollInterval(query.state.data),
    ...config,
  });
}
