import { queryOptions, useQuery } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";

import type { RepositoryImportError } from "@/entities/repository/domain/model/branch-repository";
import {
  type GetRepositoryImportTaskParams,
  getImportTaskErrorMessage,
  getRepositoryImportTask,
} from "@/entities/repository/domain/use-cases/get-repository-import-error";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  MAX_IMPORT_TASK_LOOKUPS,
  REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

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
    retry: retryBackgroundQuery,
    refetchInterval: (query) => {
      const isStillLookingForTask =
        query.state.data === null && query.state.dataUpdateCount < MAX_IMPORT_TASK_LOOKUPS;

      return pollWhileHealthy(
        isSyncing || isStillLookingForTask,
        REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
        query
      );
    },
  });
}

// A finished task's log doesn't change, so it is fetched once per task.
export function getImportTaskErrorMessageQueryOptions(taskId: string | null | undefined) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importLog(taskId ?? ""),
    queryFn: () => getImportTaskErrorMessage(taskId ?? ""),
    enabled: !!taskId,
    staleTime: Number.POSITIVE_INFINITY,
    retry: retryBackgroundQuery,
  });
}

// A failed lookup reads as "details not found", so the band stays up whatever happens here.
export function useGetRepositoryImportError(
  params: GetRepositoryImportTaskQueryParams
): RepositoryImportError | undefined {
  const task = useQuery(getRepositoryImportTaskQueryOptions(params));
  const taskId = task.data;
  const log = useQuery(getImportTaskErrorMessageQueryOptions(taskId));

  if (taskId === undefined) return task.isError ? { status: "not-found", taskId: null } : undefined;
  if (taskId === null) return { status: "not-found", taskId: null };
  if (log.data === undefined) return log.isError ? { status: "not-found", taskId } : undefined;

  return log.data === null
    ? { status: "not-found", taskId }
    : { status: "found", taskId, message: log.data };
}
