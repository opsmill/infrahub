import { queryOptions, useQuery } from "@tanstack/react-query";

import { isRepositoryAccessDenied } from "@/entities/repository/domain/rules/branch-repositories-error";
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
    refetchInterval: (query) =>
      !isRepositoryAccessDenied(query.state.error) && isAnyRepositorySyncing(query.state.data)
        ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS
        : false,
  });
}

export function useGetBranchRepositoryHealth(params: GetBranchRepositoryHealthParams) {
  return useQuery(getBranchRepositoryHealthQueryOptions(params));
}
