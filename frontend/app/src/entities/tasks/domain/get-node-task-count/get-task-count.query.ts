import {
  GetTaskCountParams,
  getTaskCount,
} from "@/entities/tasks/domain/get-node-task-count/get-task-count";
import { QueryConfig } from "@/shared/api/types";
import { queryOptions, useQuery } from "@tanstack/react-query";

export function getTaskCountQueryOptions(params: GetTaskCountParams) {
  return queryOptions({
    queryKey: ["objects", params.nodeId, "tasks", "count"],
    queryFn: () => getTaskCount(params),
  });
}

export type useGetTaskCountOptions = QueryConfig<typeof getTaskCountQueryOptions>;

export function useGetTaskCount(params: GetTaskCountParams, config: useGetTaskCountOptions = {}) {
  return useQuery({
    ...getTaskCountQueryOptions(params),
    ...config,
  });
}
