import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetRepositoryImportErrorParams,
  getRepositoryImportError,
} from "@/entities/repository/domain/use-cases/get-repository-import-error";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

const SYNCING_REFETCH_INTERVAL_MS = 10_000;

export interface GetRepositoryImportErrorQueryParams extends GetRepositoryImportErrorParams {
  isSyncing: boolean;
}

export function getRepositoryImportErrorQueryOptions({
  branchName,
  repositoryId,
  isSyncing,
}: GetRepositoryImportErrorQueryParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importError({ branchName, repositoryId }),
    queryFn: () => getRepositoryImportError({ branchName, repositoryId }),
    refetchInterval: isSyncing ? SYNCING_REFETCH_INTERVAL_MS : false,
  });
}

export type UseGetRepositoryImportErrorOptions = QueryConfig<
  typeof getRepositoryImportErrorQueryOptions
>;

export function useGetRepositoryImportError(
  params: GetRepositoryImportErrorQueryParams,
  config: UseGetRepositoryImportErrorOptions = {}
) {
  return useQuery({
    ...getRepositoryImportErrorQueryOptions(params),
    ...config,
  });
}
