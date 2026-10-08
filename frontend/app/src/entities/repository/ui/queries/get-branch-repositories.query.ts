import { queryOptions, useQuery } from "@tanstack/react-query";

import { keepPreviousDataWithin } from "@/shared/api/keep-previous-data-within";
import { getOffset } from "@/shared/utils/table-pagination";

import { isRepositoryAccessDenied } from "@/entities/repository/domain/rules/branch-repositories-error";
import { isRepositorySyncing } from "@/entities/repository/domain/rules/repository-syncing";
import {
  type GetBranchRepositoriesParams,
  getBranchRepositories,
} from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/repository-polling";

interface GetBranchRepositoriesQueryParams extends GetBranchRepositoriesParams {
  isSyncing: boolean;
}

export function getBranchRepositoriesQueryOptions({
  isSyncing,
  ...params
}: GetBranchRepositoriesQueryParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchRepositories(params),
    queryFn: () => getBranchRepositories(params),
    // Rows still showing a sync are fetched again after the health says it ended, so they catch up.
    refetchInterval: (query) =>
      !isRepositoryAccessDenied(query.state.error) &&
      (isSyncing || !!query.state.data?.repositories.some(isRepositorySyncing))
        ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS
        : false,
    placeholderData: keepPreviousDataWithin(
      repositoryQueryKeys.branchRepositoryList({
        branchName: params.branchName,
        syncWithGit: params.syncWithGit,
      })
    ),
  });
}

interface UseGetBranchRepositoriesParams {
  branchName: string;
  syncWithGit: boolean;
  isSyncing: boolean;
  page: number;
  pageSize: number;
}

export function useGetBranchRepositories({
  page,
  pageSize,
  ...params
}: UseGetBranchRepositoriesParams) {
  return useQuery(
    getBranchRepositoriesQueryOptions({
      ...params,
      limit: pageSize,
      offset: getOffset(page, pageSize),
    })
  );
}
