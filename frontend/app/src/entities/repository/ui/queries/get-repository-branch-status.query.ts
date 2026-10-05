import { queryOptions } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";

import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";
import type { RepositoryBranchStatusPage } from "@/entities/repository/domain/model/repository-branch-status";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/repository-polling";

const STATUS_STALE_TIME_MS = 60_000;

function isAnyBranchSyncing(page: RepositoryBranchStatusPage | undefined): boolean {
  return (
    page?.rows.some((row) => row.syncStatus?.value === REPOSITORY_SYNC_STATUS_SYNCING) ?? false
  );
}

export function getRepositoryBranchStatusQueryOptions(params: GetRepositoryBranchStatusParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchStatus(params),
    queryFn: () => getRepositoryBranchStatus(params),
    staleTime: STATUS_STALE_TIME_MS,
    retry: retryBackgroundQuery,
    refetchInterval: (query) =>
      pollWhileHealthy(
        isAnyBranchSyncing(query.state.data),
        REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
        query
      ),
  });
}
