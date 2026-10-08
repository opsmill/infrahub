import { type QueryStatus, queryOptions } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";

import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";
import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/repository-polling";

const STATUS_STALE_TIME_MS = 60_000;

function isAnyBranchSyncing(page: RepositoryBranchStatusPage | undefined): boolean {
  return (
    page?.rows.some((row) => row.syncStatus?.value === REPOSITORY_SYNC_STATUS_SYNCING) ?? false
  );
}

interface RepositoryBranchStatusQuery {
  state: { data: RepositoryBranchStatusPage | undefined; status: QueryStatus; error: Error | null };
}

export function getRepositoryBranchStatusRefetchInterval(
  query: RepositoryBranchStatusQuery
): number | false {
  return pollWhileHealthy(
    isAnyBranchSyncing(query.state.data),
    REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
    query
  );
}

export function getRepositoryBranchStatusQueryOptions(params: GetRepositoryBranchStatusParams) {
  return queryOptions({
    queryKey: branchGitStatusQueryKeys.repositoryBranchStatus(params),
    queryFn: () => getRepositoryBranchStatus(params),
    staleTime: STATUS_STALE_TIME_MS,
    retry: retryBackgroundQuery,
    refetchInterval: getRepositoryBranchStatusRefetchInterval,
  });
}
