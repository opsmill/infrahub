import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { isRepositorySyncing } from "@/entities/repository/domain/rules/is-repository-syncing";
import {
  type GetBranchRepositoriesParams,
  getBranchRepositories,
  getRepositoryListKind,
} from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

const SYNCING_REFETCH_INTERVAL_MS = 10_000;

function isAnyRepositorySyncing(result: BranchRepositoriesResult | undefined): boolean {
  return result?.status === "ok" && result.repositories.some(isRepositorySyncing);
}

export function getBranchRepositoriesQueryOptions(params: GetBranchRepositoriesParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branch({
      branchName: params.branchName,
      kind: getRepositoryListKind(params.syncWithGit),
    }),
    queryFn: () => getBranchRepositories(params),
    refetchInterval: (query) =>
      isAnyRepositorySyncing(query.state.data) ? SYNCING_REFETCH_INTERVAL_MS : false,
  });
}

export type UseGetBranchRepositoriesOptions = QueryConfig<typeof getBranchRepositoriesQueryOptions>;

export function useGetBranchRepositories(
  params: GetBranchRepositoriesParams,
  config: UseGetBranchRepositoriesOptions = {}
) {
  return useQuery({
    ...getBranchRepositoriesQueryOptions(params),
    ...config,
  });
}
