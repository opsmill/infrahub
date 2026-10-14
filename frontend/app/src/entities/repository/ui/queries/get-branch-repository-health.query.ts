import { queryOptions, useQuery } from "@tanstack/react-query";

import { isRepositoryAccessDenied } from "@/entities/repository/domain/rules/branch-repositories-error";
import { isAnyRepositorySyncing } from "@/entities/repository/domain/rules/repository-syncing";
import {
  type GetBranchRepositoryHealthParams,
  getBranchRepositoryHealth,
} from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
  REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

// Each failing list stops here; the server's total still counts the rest.
const REPOSITORY_HEALTH_LIST_LIMIT = 50;

type GetBranchRepositoryHealthQueryParams = Omit<GetBranchRepositoryHealthParams, "limit">;

export function getBranchRepositoryHealthQueryOptions(
  queryParams: GetBranchRepositoryHealthQueryParams
) {
  const params = { ...queryParams, limit: REPOSITORY_HEALTH_LIST_LIMIT };

  return queryOptions({
    queryKey: repositoryQueryKeys.branchHealth(params),
    queryFn: () => getBranchRepositoryHealth(params),
    refetchInterval: ({ state }) => {
      if (isRepositoryAccessDenied(state.error)) return false;
      if (state.status === "error") return REPOSITORY_ERROR_REFETCH_INTERVAL_MS;
      return isAnyRepositorySyncing(state.data) ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS : false;
    },
  });
}

export function useGetBranchRepositoryHealth(params: GetBranchRepositoryHealthQueryParams) {
  return useQuery(getBranchRepositoryHealthQueryOptions(params));
}
