import { queryOptions, useQuery } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";

import { isAnyRepositorySyncing } from "@/entities/repository/domain/rules/is-any-repository-syncing";
import {
  type GetBranchRepositoryHealthParams,
  getBranchRepositoryHealth,
} from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/repository-polling";

export function getBranchRepositoryHealthQueryOptions(params: GetBranchRepositoryHealthParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchHealth(params),
    queryFn: () => getBranchRepositoryHealth(params),
    retry: retryBackgroundQuery,
    refetchInterval: (query) =>
      pollWhileHealthy(
        isAnyRepositorySyncing(query.state.data),
        REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
        query
      ),
  });
}

export function useGetBranchRepositoryHealth(params: GetBranchRepositoryHealthParams) {
  return useQuery(getBranchRepositoryHealthQueryOptions(params));
}
