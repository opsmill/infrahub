import { queryOptions } from "@tanstack/react-query";

import { useCountClampedQuery } from "@/shared/hooks/use-count-clamped-query";

import { REPOSITORY_SYNC_STATUS_SYNCING } from "@/entities/repository/domain/model/repository";
import {
  type GetBranchRepositoriesParams,
  getBranchRepositories,
} from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/get-branch-repository-health.query";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

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
    refetchInterval: (query) =>
      isSyncing ||
      query.state.data?.repositories.some(
        ({ syncStatus }) => syncStatus.value === REPOSITORY_SYNC_STATUS_SYNCING
      )
        ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS
        : false,
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
