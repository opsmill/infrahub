import { queryOptions, useQuery } from "@tanstack/react-query";

import { isAnyRepositorySyncing } from "@/entities/repository/domain/rules/is-any-repository-syncing";
import {
  type GetBranchRepositoryHealthParams,
  getBranchRepositoryHealth,
} from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export const REPOSITORY_SYNC_REFETCH_INTERVAL_MS = 10_000;

export function getBranchRepositoryHealthQueryOptions(params: GetBranchRepositoryHealthParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchHealth(params),
    queryFn: () => getBranchRepositoryHealth(params),
    refetchInterval: (query) =>
      query.state.status === "error" || isAnyRepositorySyncing(query.state.data)
        ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS
        : false,
  });
}

export function useGetBranchRepositoryHealth(params: GetBranchRepositoryHealthParams) {
  return useQuery(getBranchRepositoryHealthQueryOptions(params));
}
