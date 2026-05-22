import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type CheckTaskDetailsParams,
  checkTaskDetails,
} from "@/entities/tasks/domain/check-task-details/check-task-details";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

export function checkTaskDetailsQueryOptions(params: CheckTaskDetailsParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.check(params),
    queryFn: () => checkTaskDetails(params),
  });
}

export type UseCheckTaskDetailsOptions = QueryConfig<typeof checkTaskDetailsQueryOptions>;

export function useCheckTaskDetails(
  params: CheckTaskDetailsParams,
  config?: UseCheckTaskDetailsOptions
) {
  return useQuery({
    ...checkTaskDetailsQueryOptions(params),
    ...config,
  });
}
