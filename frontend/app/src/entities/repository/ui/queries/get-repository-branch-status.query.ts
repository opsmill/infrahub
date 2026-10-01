import { queryOptions } from "@tanstack/react-query";

import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";
import type { RepositoryBranchStatusPage } from "@/entities/repository/domain/model/repository-branch-status";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

const STATUS_STALE_TIME_MS = 60_000;
const SYNCING_REFETCH_INTERVAL_MS = 10_000;

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
    refetchInterval: (query) =>
      isAnyBranchSyncing(query.state.data) ? SYNCING_REFETCH_INTERVAL_MS : false,
  });
}
