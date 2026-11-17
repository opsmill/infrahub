import { queryOptions, skipToken, useQuery } from "@tanstack/react-query";

import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode } from "@/shared/api/graphql/error-handling";

import type { RepositoryImportError } from "@/entities/repository/domain/model/branch-repository";
import { getImportTaskErrorMessage } from "@/entities/repository/domain/use-cases/get-import-task-error-message";
import {
  type GetLatestRepositoryImportTaskParams,
  getLatestRepositoryImportTask,
} from "@/entities/repository/domain/use-cases/get-latest-repository-import-task";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
  REPOSITORY_SYNC_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

// Logs come back oldest first, so anything below the backend's 10 000-line cap can cut off the final error line.
const IMPORT_LOG_LIMIT = 10_000;

interface GetLatestRepositoryImportTaskQueryParams extends GetLatestRepositoryImportTaskParams {
  isSyncing: boolean;
}

export function getLatestRepositoryImportTaskQueryOptions({
  isSyncing,
  ...params
}: GetLatestRepositoryImportTaskQueryParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.latestImportTask(params),
    queryFn: () => getLatestRepositoryImportTask(params),
    // A run can still be ending as failed after the repository already shows the import error.
    refetchInterval: ({ state }) => {
      if (hasOnlyThrownCatalogueCode(state.error, ERROR_CODES.PERMISSION_DENIED)) return false;
      if (state.status === "error") return REPOSITORY_ERROR_REFETCH_INTERVAL_MS;
      return isSyncing || state.data?.status === "running"
        ? REPOSITORY_SYNC_REFETCH_INTERVAL_MS
        : false;
    },
  });
}

// A finished task's log doesn't change, so it is fetched once per task.
export function getImportTaskErrorMessageQueryOptions({ taskId }: { taskId: string | undefined }) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importLog({ taskId: taskId ?? "" }),
    queryFn: taskId
      ? () => getImportTaskErrorMessage({ taskId, logLimit: IMPORT_LOG_LIMIT })
      : skipToken,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

// A failed lookup reads as "details not found", so the band stays up whatever happens here.
export function useGetRepositoryImportError(
  params: GetLatestRepositoryImportTaskQueryParams
): RepositoryImportError | undefined {
  const { data: task, isError } = useQuery(getLatestRepositoryImportTaskQueryOptions(params));
  const taskId = task?.status === "failed" ? task.taskId : undefined;
  const log = useQuery(getImportTaskErrorMessageQueryOptions({ taskId }));

  if (!task) return isError ? { status: "not-found", taskId: null } : undefined;
  if (task.status === "running") return undefined;
  if (task.status === "none") return { status: "not-found", taskId: null };
  if (log.data === undefined) {
    return log.isError ? { status: "not-found", taskId: task.taskId } : undefined;
  }

  return log.data === null
    ? { status: "not-found", taskId: task.taskId }
    : { status: "found", taskId: task.taskId, message: log.data };
}
