import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";

import {
  type GetTaskListParams,
  getTaskList,
} from "@/entities/tasks/domain/get-task-list/get-task-list";
import { tasksQueryKeys } from "@/entities/tasks/domain/tasks.query-keys";

export function getTaskListQueryOptions(params: GetTaskListParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.list(params),
    queryFn: () => getTaskList(params),
  });
}

export function useGetTaskList(
  params?: GetTaskListParams,
  config?: QueryConfig<typeof getTaskListQueryOptions>
) {
  const [{ offset, limit }] = usePagination();

  return useQuery({
    ...getTaskListQueryOptions({ ...params, offset, limit }),
    ...config,
  });
}
