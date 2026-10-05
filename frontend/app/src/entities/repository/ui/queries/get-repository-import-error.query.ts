import { queryOptions, useQuery } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";

import type {
  RepositoryImportError,
  RepositoryImportTaskLookup,
} from "@/entities/repository/domain/model/branch-repository";
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

// Only consecutive "nothing found" answers count against the lookup budget: a running import is
// expected to end as a failed run, so it is polled for as long as it runs.
interface RepositoryImportTaskLookupResult {
  lookup: RepositoryImportTaskLookup;
  notFoundCount: number;
}

export function getRepositoryImportTaskQueryOptions({
  isSyncing,
  ...params
}: GetRepositoryImportTaskQueryParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.importTask(params),
    queryFn: async ({ client, queryKey }): Promise<RepositoryImportTaskLookupResult> => {
      const lookup = await getRepositoryImportTask(params);
      const previous = client.getQueryData<RepositoryImportTaskLookupResult>(queryKey);
      const notFoundCount = lookup.status === "not-found" ? (previous?.notFoundCount ?? 0) + 1 : 0;
      return { lookup, notFoundCount };
    },
    retry: retryBackgroundQuery,
    refetchInterval: (query) => {
      const { data, status } = query.state;
      const isStillLookingForTask =
        status === "error" ||
        data?.lookup.status === "running" ||
        (data?.lookup.status === "not-found" && data.notFoundCount < MAX_IMPORT_TASK_LOOKUPS);

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
  const lookup = task.data?.lookup;
  const taskId = lookup?.status === "failed" ? lookup.taskId : undefined;
  const log = useQuery(getImportTaskErrorMessageQueryOptions(taskId));

  if (!lookup) return task.isError ? { status: "not-found", taskId: null } : undefined;
  if (lookup.status === "running") return undefined;
  if (lookup.status === "not-found") return { status: "not-found", taskId: null };
  if (log.data === undefined) return log.isError ? { status: "not-found", taskId } : undefined;

  return log.data === null
    ? { status: "not-found", taskId }
    : { status: "found", taskId, message: log.data };
}
