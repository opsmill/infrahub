import { queryOptions, useQuery } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { GetTasksFromApiParams } from "@/entities/tasks/api/get-tasks-from-api";
import { getTasks } from "@/entities/tasks/domain/get-tasks/get-tasks";
import { tasksQueryKeys } from "@/entities/tasks/domain/tasks.query-keys";

interface GetTasksHomepageParams extends Omit<GetTasksFromApiParams, "branchName"> {}

export function getTasksHomepageQueryOptions(params: GetTasksFromApiParams) {
  return queryOptions({
    queryKey: [...objectQueryKeys.all, ...tasksQueryKeys.all, ...tasksQueryKeys.filters(params)],
    queryFn: () => getTasks(params),
  });
}

export function useGetTasksHomepage(params: GetTasksHomepageParams) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getTasksHomepageQueryOptions({ ...params, branchName: currentBranch.name }),
  });
}
