import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetTaskCountParams,
  getTaskCount,
} from "@/entities/tasks/domain/get-node-task-count/get-task-count";
import { ContextParams, QueryConfig } from "@/shared/api/types";
import { queryOptions, useQuery } from "@tanstack/react-query";

export function getTaskCountQueryOptions(params: GetTaskCountParams) {
  return queryOptions({
    queryKey: [params.branchName, "objects", params.nodeId, "tasks", "count"],
    queryFn: () => getTaskCount(params),
  });
}

export type useGetTaskCountOptions = QueryConfig<typeof getTaskCountQueryOptions>;

export function useGetTaskCount(
  params: Omit<GetTaskCountParams, keyof ContextParams>,
  config: useGetTaskCountOptions = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getTaskCountQueryOptions({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
