import { queryOptions, useQuery } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { GetTasksFromApiParams } from "@/entities/tasks/api/get-tasks-from-api";
import { getTasksHomepage } from "@/entities/tasks/domain/get-tasks/get-tasks-homepage";
import { tasksQueryKeys } from "@/entities/tasks/domain/tasks.query-keys";

export interface GetTasksHomepageParams extends GetTasksFromApiParams {}

export function getTasksHomepageQueryOptions(params: GetTasksHomepageParams) {
  return queryOptions({
    queryKey: [...objectQueryKeys.all, ...tasksQueryKeys.filters(params)],
    queryFn: () => getTasksHomepage(params),
  });
}

export function useGetTasksHomepage(params: Omit<GetTasksHomepageParams, "branchName">) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getTasksHomepageQueryOptions({ ...params, branchName: currentBranch.name }),
  });
}
