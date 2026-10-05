import { queryOptions } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";
import { useCountClampedQuery } from "@/shared/hooks/use-count-clamped-query";

import { isRepositorySyncing } from "@/entities/repository/domain/rules/is-repository-syncing";
import {
  type GetBranchRepositoriesParams,
  getBranchRepositories,
} from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/repository-polling";

export interface GetBranchRepositoriesQueryParams extends GetBranchRepositoriesParams {
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
    retry: retryBackgroundQuery,
    refetchInterval: (query) =>
      pollWhileHealthy(
        isSyncing || !!query.state.data?.repositories.some(isRepositorySyncing),
        REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
        query
      ),
    // Keeps the previous page on screen while the next one loads, within one branch and list only.
    placeholderData: (previousData, previousQuery) => {
      const previousParams = previousQuery?.queryKey.at(-1) as
        | GetBranchRepositoriesParams
        | undefined;
      const isSameList =
        previousParams?.branchName === params.branchName &&
        previousParams?.syncWithGit === params.syncWithGit;

      return isSameList ? previousData : undefined;
    },
  });
}

export interface UseGetBranchRepositoriesParams {
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
  return useCountClampedQuery({ page, pageSize }, (offset) =>
    getBranchRepositoriesQueryOptions({ ...params, limit: pageSize, offset })
  );
}
