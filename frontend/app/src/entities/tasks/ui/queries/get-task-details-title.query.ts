import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetTaskDetailsTitleParams,
  getTaskDetailsTitle,
} from "@/entities/tasks/domain/get-task-details-title/get-task-details-title";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function getTaskDetailsTitleQueryOptions(params: GetTaskDetailsTitleParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.detailsTitle(params),
    queryFn: () => getTaskDetailsTitle(params),
  });
}

export function useGetTaskDetailsTitle(
  params: GetTaskDetailsTitleParams,
  config?: QueryConfig<typeof getTaskDetailsTitleQueryOptions>
) {
  return useQuery({
    ...getTaskDetailsTitleQueryOptions(params),
    ...config,
  });
}
