import { queryOptions, useQuery } from "@tanstack/react-query";

import type { ContextParams, QueryConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import {
  type GetTaskCountParams,
  getTaskCount,
} from "@/entities/tasks/domain/get-node-task-count/get-task-count";

export function getTaskCountQueryOptions(params: GetTaskCountParams) {
  return queryOptions({
    queryKey: [...objectQueryKeys.all, params.branchName, params.nodeId, "tasks", "count"],
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
