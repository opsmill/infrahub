import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetTaskDetailsParams,
  getTaskDetails,
} from "@/entities/tasks/domain/get-task-details/get-task-details";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function getTaskDetailsQueryOptions(params?: GetTaskDetailsParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.details(params),
    queryFn: () => getTaskDetails(params),
  });
}

export function useGetTaskDetails(
  params?: GetTaskDetailsParams,
  config?: QueryConfig<typeof getTaskDetailsQueryOptions>
) {
  return useQuery({
    ...getTaskDetailsQueryOptions(params),
    ...config,
  });
}
