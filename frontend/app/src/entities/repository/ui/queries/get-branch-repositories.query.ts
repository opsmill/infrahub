import { queryOptions, useQuery } from "@tanstack/react-query";

import { getOffset } from "@/shared/utils/table-pagination";

import { isRepositoryAccessDenied } from "@/entities/repository/domain/rules/branch-repositories-error";
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

const isListParams = (
  value: unknown
): value is Pick<GetBranchRepositoriesParams, "branchName" | "syncWithGit"> =>
  typeof value === "object" &&
  value !== null &&
  "branchName" in value &&
  typeof value.branchName === "string" &&
  "syncWithGit" in value &&
  typeof value.syncWithGit === "boolean";

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
    // Keeps the previous page on screen while the next one loads, within one branch and list only.
    placeholderData: (previousData, previousQuery) => {
      const previousParams: unknown = previousQuery?.queryKey.at(-1);
      const isSameList =
        isListParams(previousParams) &&
        previousParams.branchName === params.branchName &&
        previousParams.syncWithGit === params.syncWithGit;

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
  return useQuery(
    getBranchRepositoriesQueryOptions({
      ...params,
      limit: pageSize,
      offset: getOffset(page, pageSize),
    })
  );
}
