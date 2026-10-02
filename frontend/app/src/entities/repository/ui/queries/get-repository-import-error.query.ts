import { queryOptions, useQuery } from "@tanstack/react-query";

import type { RepositoryImportError } from "@/entities/repository/domain/model/branch-repository";
import {
  type GetRepositoryImportTaskParams,
  getImportTaskErrorMessage,
  getRepositoryImportTask,
} from "@/entities/repository/domain/use-cases/get-repository-import-error";
import { REPOSITORY_SYNC_REFETCH_INTERVAL_MS } from "@/entities/repository/ui/queries/get-branch-repository-health.query";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export interface GetRepositoryImportTaskQueryParams extends GetRepositoryImportTaskParams {
  isSyncing: boolean;
}

export function getRepositoryImportTaskQueryOptions({
  isSyncing,
  ...params
}: GetRepositoryImportTaskQueryParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importTask(params),
    queryFn: () => getRepositoryImportTask(params),
    refetchInterval: isSyncing ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS : false,
  });
}

// A finished task's log doesn't change, so it is fetched once per task; a failed fetch is retried.
export function getImportTaskErrorMessageQueryOptions(taskId: string | null | undefined) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importLog(taskId ?? ""),
    queryFn: () => getImportTaskErrorMessage(taskId ?? ""),
    enabled: !!taskId,
    staleTime: Number.POSITIVE_INFINITY,
    refetchInterval: (query) =>
      query.state.status === "error" ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS : false,
  });
}

export function useGetRepositoryImportError(
  params: GetRepositoryImportTaskQueryParams
): RepositoryImportError | undefined {
  const task = useQuery(getRepositoryImportTaskQueryOptions(params));
  const taskId = task.data;
  const log = useQuery(getImportTaskErrorMessageQueryOptions(taskId));

  if (taskId === undefined) return undefined;
  if (taskId === null) return { status: "not-found", taskId: null };
  if (log.data === undefined) return log.isError ? { status: "not-found", taskId } : undefined;

  return log.data === null
    ? { status: "not-found", taskId }
    : { status: "found", taskId, message: log.data };
}
