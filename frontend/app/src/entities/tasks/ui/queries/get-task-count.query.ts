import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetTaskCountParams,
  getTaskCount,
} from "@/entities/tasks/domain/get-node-task-count/get-task-count";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function getTaskCountQueryOptions(params?: GetTaskCountParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.count(params),
    queryFn: () => getTaskCount(params),
  });
}

export type useGetTaskCountOptions = QueryConfig<typeof getTaskCountQueryOptions>;

export function useGetTaskCount(params?: GetTaskCountParams, config?: useGetTaskCountOptions) {
  return useQuery({
    ...getTaskCountQueryOptions(params),
    ...config,
  });
}
