import { type QueryStatus, queryOptions } from "@tanstack/react-query";

import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import { isBranchGitStatusAccessDenied } from "@/entities/branch-git-status/domain/rules/to-branch-git-status-error";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/branch-git-status/domain/use-cases/get-repository-branch-status";
import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";
import {
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
  REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

const STATUS_STALE_TIME_MS = 60_000;

function isAnyBranchSyncing(page: RepositoryBranchStatusPage | undefined): boolean {
  return (
    page?.rows.some((row) => row.syncStatus?.value === REPOSITORY_SYNC_STATUS_SYNCING) ?? false
  );
}

interface RepositoryBranchStatusQuery {
  state: { data: RepositoryBranchStatusPage | undefined; status: QueryStatus; error: Error | null };
}

export function getRepositoryBranchStatusRefetchInterval({
  state,
}: RepositoryBranchStatusQuery): number | false {
  if (isBranchGitStatusAccessDenied(state.error)) return false;
  if (state.status === "error") return REPOSITORY_ERROR_REFETCH_INTERVAL_MS;
  return isAnyBranchSyncing(state.data) ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS : false;
}

export function getRepositoryBranchStatusQueryOptions(params: GetRepositoryBranchStatusParams) {
  return queryOptions({
    queryKey: branchGitStatusQueryKeys.repositoryBranchStatus(params),
    queryFn: () => getRepositoryBranchStatus(params),
    staleTime: STATUS_STALE_TIME_MS,
    refetchInterval: getRepositoryBranchStatusRefetchInterval,
  });
}
